from flask import Flask, request, render_template, redirect, url_for, jsonify, send_file, flash, session
import os
import csv
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
from io import BytesIO, StringIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from pymongo import MongoClient
from bson.objectid import ObjectId
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["SECRET_KEY"] = "your-secret-key"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# MongoDB connection with error handling
try:
    client = MongoClient("mongodb://mongodb:27017/", serverSelectionTimeoutMS=5000)
    client.server_info()  # Test connection
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise SystemExit("MongoDB connection failed")

db = client["bachat_gat_db"]
members_collection = db["members"]
groups_collection = db["groups"]
users_collection = db["users"]

class Member:
    def __init__(self, id, name, email, mobile, group_id, photo_path=None, savings=0.0, loan=0.0, loan_date=None, transactions=None):
        self.id = str(id)
        self.name = name
        self.email = email
        self.mobile = mobile
        self.group_id = str(group_id)
        self.photo_path = photo_path
        self.savings = float(savings)
        self.loan = float(loan)
        self.loan_date = loan_date if loan_date else None
        self.transactions = transactions if transactions else []

    def calculate_monthly_repayment(self, months=12):
        group = groups_collection.find_one({"_id": ObjectId(self.group_id)})
        interest_rate = group["interest_rate"]
        if self.loan > 0 and self.loan_date:
            total_with_interest = self.loan * (1 + interest_rate)
            return total_with_interest / months
        return 0.0

    @staticmethod
    def from_dict(data):
        return Member(
            id=data["_id"],
            name=data["name"],
            email=data["email"],
            mobile=data["mobile"],
            group_id=data["group_id"],
            photo_path=data.get("photo_path"),
            savings=data.get("savings", 0.0),
            loan=data.get("loan", 0.0),
            loan_date=data.get("loan_date"),
            transactions=data.get("transactions", [])
        )

class Group:
    def __init__(self, id, name, interest_rate, address, image_path=None, group_savings=0.0, last_interest_update=None):
        self.id = str(id)
        self.name = name
        self.interest_rate = float(interest_rate)
        self.address = address
        self.image_path = image_path
        self.group_savings = float(group_savings)
        self.last_interest_update = last_interest_update if last_interest_update else datetime.now().isoformat()

    @staticmethod
    def from_dict(data):
        return Group(
            id=data["_id"],
            name=data["name"],
            interest_rate=data["interest_rate"],
            address=data["address"],
            image_path=data.get("image_path"),
            group_savings=data.get("group_savings", 0.0),
            last_interest_update=data.get("last_interest_update")
        )

def update_group_savings(group_id):
    group_data = groups_collection.find_one({"_id": ObjectId(group_id)})
    now = datetime.now()
    last_update = datetime.fromisoformat(group_data["last_interest_update"])
    if (now - last_update).days >= 30:
        total_loan_interest = sum(m["loan"] * group_data["interest_rate"] / 12 for m in members_collection.find({"group_id": group_id, "loan": {"$gt": 0}}))
        new_group_savings = group_data["group_savings"] + total_loan_interest
        groups_collection.update_one({"_id": ObjectId(group_id)}, {"$set": {"group_savings": new_group_savings, "last_interest_update": now.isoformat()}})

def recalculate_member_fields(member_data):
    savings = sum(t["amount"] for t in member_data["transactions"] if t["type"] == "Savings")
    loan = sum(t["amount"] for t in member_data["transactions"] if t["type"] == "Loan") - \
           sum(t["amount"] for t in member_data["transactions"] if t["type"] == "Repayment")
    loan_date = max([t["date"] for t in member_data["transactions"] if t["type"] == "Loan"], default=None) if loan > 0 else None
    return {
        "savings": savings,
        "loan": max(0.0, loan),
        "loan_date": loan_date
    }

def login_required(f):
    def wrap(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

def admin_required(f):
    def wrap(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first")
            return redirect(url_for("login"))
        user = users_collection.find_one({"_id": ObjectId(session["user_id"])})
        if user["role"] != "admin":
            flash("Admin access required")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        if not username or not password or role not in ["admin", "member"]:
            flash("Invalid input")
            return redirect(url_for("register"))

        if users_collection.find_one({"username": username}):
            flash("Username already exists")
            return redirect(url_for("register"))

        user_data = {
            "username": username,
            "password": generate_password_hash(password),
            "role": role
        }
        result = users_collection.insert_one(user_data)
        flash("Registration successful, please login")
        logger.info(f"Registered user: {username}, role: {role}")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = users_collection.find_one({"username": username})
        if user and check_password_hash(user["password"], password):
            session["user_id"] = str(user["_id"])
            session["role"] = user["role"]
            flash("Login successful")
            logger.info(f"User logged in: {username}, role: {user['role']}")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("role", None)
    flash("Logged out successfully")
    return redirect(url_for("login"))

@app.route("/", methods=["GET"])
@login_required
def index():
    groups = {str(g["_id"]): Group.from_dict(g) for g in groups_collection.find()}
    selected_group_id = request.args.get("group_id")
    if selected_group_id and groups.get(selected_group_id):
        update_group_savings(selected_group_id)
        members = {str(m["_id"]): Member.from_dict(m) for m in members_collection.find({"group_id": ObjectId(selected_group_id)})}
        group = groups[selected_group_id]
    else:
        members = {}
        group = None
    return render_template("index.html", groups=groups, members=members, group=group, selected_group_id=selected_group_id, user_role=session.get("role"))

@app.route("/create_group", methods=["POST"])
@login_required
@admin_required
def create_group():
    name = request.form["name"]
    interest_rate = float(request.form["interest_rate"]) / 100
    address = request.form["address"]
    image = request.files.get("image")

    if not all([name, interest_rate, address]):
        return "All fields required", 400

    image_path = None
    if image:
        filename = secure_filename(f"group_{ObjectId()}_{image.filename}")
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        image.save(image_path)
        Image.open(image_path).resize((64, 64)).save(image_path)

    group_data = {
        "name": name,
        "interest_rate": interest_rate,
        "address": address,
        "image_path": image_path,
        "group_savings": 0.0,
        "last_interest_update": datetime.now().isoformat()
    }
    result = groups_collection.insert_one(group_data)
    return redirect(url_for("index", group_id=str(result.inserted_id)))

@app.route("/add_member", methods=["POST"])
@login_required
@admin_required
def add_member():
    group_id = request.form.get("group_id")
    name = request.form.get("name")
    email = request.form.get("email")
    mobile = request.form.get("mobile")
    photo = request.files.get("photo")

    if not group_id or not groups_collection.find_one({"_id": ObjectId(group_id)}):
        return "Invalid or missing group ID", 400
    if not all([name, email, mobile]):
        return "Name, email, and mobile are required", 400

    photo_path = None
    if photo:
        filename = secure_filename(f"{ObjectId()}_{photo.filename}")
        photo_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        photo.save(photo_path)
        Image.open(photo_path).resize((32, 32)).save(photo_path)

    member_data = {
        "group_id": ObjectId(group_id),
        "name": name,
        "email": email,
        "mobile": mobile,
        "photo_path": photo_path,
        "savings": 0.0,
        "loan": 0.0,
        "loan_date": None,
        "transactions": []
    }
    result = members_collection.insert_one(member_data)
    return redirect(url_for("index", group_id=group_id))

@app.route("/import_members", methods=["POST"])
@login_required
@admin_required
def import_members():
    group_id = request.form.get("group_id")
    if not group_id or not groups_collection.find_one({"_id": ObjectId(group_id)}):
        flash("Invalid or missing group ID")
        logger.error(f"Invalid or missing group ID: {group_id}")
        return redirect(url_for("index"))

    file = request.files.get("member_file")
    if not file or not file.filename.endswith(".csv"):
        flash("Please upload a valid CSV file")
        logger.error("No file uploaded or file is not a CSV")
        return redirect(url_for("index", group_id=group_id))

    try:
        logger.info(f"Processing member file: {file.filename}")
        stream = StringIO(file.stream.read().decode("utf-8"))
        csv_reader = csv.DictReader(stream)
        required_columns = {"name", "email", "mobile"}
        if not required_columns.issubset(csv_reader.fieldnames):
            flash("CSV must contain columns: name, email, mobile")
            logger.error(f"Missing required columns: {csv_reader.fieldnames}")
            return redirect(url_for("index", group_id=group_id))

        imported_count = 0
        for row in csv_reader:
            logger.debug(f"Processing member row: {row}")
            name = row["name"].strip()
            email = row["email"].strip()
            mobile = row["mobile"].strip()

            if not all([name, email, mobile]):
                flash(f"Missing data in row: {row}")
                logger.warning(f"Missing data in row: {row}")
                continue

            if members_collection.find_one({"group_id": ObjectId(group_id), "$or": [{"email": email}, {"mobile": mobile}]}):
                flash(f"Member with email {email} or mobile {mobile} already exists")
                logger.warning(f"Duplicate member: email={email}, mobile={mobile}")
                continue

            member_data = {
                "group_id": ObjectId(group_id),
                "name": name,
                "email": email,
                "mobile": mobile,
                "photo_path": None,
                "savings": 0.0,
                "loan": 0.0,
                "loan_date": None,
                "transactions": []
            }
            result = members_collection.insert_one(member_data)
            if result.inserted_id:
                imported_count += 1
                logger.info(f"Added member: {name}, ID: {result.inserted_id}")

        flash(f"Successfully imported {imported_count} members")
        logger.info(f"Imported {imported_count} members for group {group_id}")
    except Exception as e:
        flash(f"Error processing file: {str(e)}")
        logger.error(f"Error processing file {file.filename}: {str(e)}")
    return redirect(url_for("index", group_id=group_id))

@app.route("/edit_member/<member_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_member(member_id):
    member_data = members_collection.find_one({"_id": ObjectId(member_id)})
    if not member_data:
        return "Member not found", 404
    member = Member.from_dict(member_data)

    if request.method == "POST":
        update_data = {
            "name": request.form["name"],
            "email": request.form["email"],
            "mobile": request.form["mobile"]
        }
        photo = request.files.get("photo")
        if photo:
            filename = secure_filename(f"{member_id}_{photo.filename}")
            photo_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            photo.save(photo_path)
            Image.open(photo_path).resize((32, 32)).save(photo_path)
            update_data["photo_path"] = photo_path
        members_collection.update_one({"_id": ObjectId(member_id)}, {"$set": update_data})
        return redirect(url_for("index", group_id=member.group_id))

    return render_template("edit_member.html", member=member)

@app.route("/delete_member/<member_id>", methods=["POST"])
@login_required
@admin_required
def delete_member(member_id):
    member_data = members_collection.find_one({"_id": ObjectId(member_id)})
    if not member_data:
        return "Member not found", 404
    group_id = member_data["group_id"]
    members_collection.delete_one({"_id": ObjectId(member_id)})
    return redirect(url_for("index", group_id=group_id))

@app.route("/transaction", methods=["POST"])
@login_required
@admin_required
def record_transaction():
    member_id = request.form["member_id"]
    amount = float(request.form["amount"])
    trans_type = request.form["type"]
    mode = request.form["mode"]
    transaction_id = request.form.get("transaction_id", "")
    date_str = request.form["date"]
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD.", 400

    member_data = members_collection.find_one({"_id": ObjectId(member_id)})
    if not member_data:
        return "Member not found", 404

    valid_modes = {"UPI", "CASH", "NEFT", "OTHER"}
    if mode not in valid_modes:
        return "Invalid transaction mode", 400

    transaction = {
        "amount": amount,
        "type": trans_type,
        "mode": mode,
        "transaction_id": transaction_id,
        "date": date
    }
    update_data = {"transactions": member_data["transactions"] + [transaction]}

    if trans_type == "Savings":
        update_data["savings"] = member_data["savings"] + amount
    elif trans_type == "Loan":
        update_data["loan"] = member_data["loan"] + amount
        update_data["loan_date"] = date
    elif trans_type == "Repayment":
        if amount > member_data["loan"]:
            return "Repayment exceeds loan", 400
        update_data["loan"] = member_data["loan"] - amount
        if update_data["loan"] == 0:
            update_data["loan_date"] = None

    members_collection.update_one({"_id": ObjectId(member_id)}, {"$set": update_data})
    update_group_savings(member_data["group_id"])
    return redirect(url_for("index", group_id=member_data["group_id"]))

@app.route("/import_transactions", methods=["POST"])
@login_required
@admin_required
def import_transactions():
    group_id = request.form.get("group_id")
    if not group_id or not groups_collection.find_one({"_id": ObjectId(group_id)}):
        flash("Invalid or missing group ID")
        logger.error(f"Invalid or missing group ID: {group_id}")
        return redirect(url_for("index"))

    file = request.files.get("transaction_file")
    if not file or not file.filename.endswith(".csv"):
        flash("Please upload a valid CSV file")
        logger.error("No file uploaded or file is not a CSV")
        return redirect(url_for("index", group_id=group_id))

    try:
        logger.info(f"Processing file: {file.filename}")
        stream = StringIO(file.stream.read().decode("utf-8"))
        csv_reader = csv.DictReader(stream)
        required_columns = {"member_id", "amount", "type", "date"}
        if not required_columns.issubset(csv_reader.fieldnames):
            flash("CSV must contain columns: member_id, amount, type, date")
            logger.error(f"Missing required columns: {csv_reader.fieldnames}")
            return redirect(url_for("index", group_id=group_id))

        valid_types = {"Savings", "Loan", "Repayment"}
        valid_modes = {"UPI", "CASH", "NEFT", "OTHER"}
        imported_count = 0
        updated_count = 0
        for row in csv_reader:
            logger.debug(f"Processing row: {row}")
            member_id = row["member_id"].strip()
            member_data = members_collection.find_one({"_id": ObjectId(member_id), "group_id": ObjectId(group_id)})
            if not member_data:
                flash(f"Member ID {member_id} not found in group")
                logger.warning(f"Member ID {member_id} not found in group {group_id}")
                continue

            try:
                amount = float(row["amount"])
                trans_type = row["type"].strip()
                mode = row.get("mode", "CASH").strip()
                transaction_id = row.get("transaction_id", "").strip()
                date_str = row["date"].strip()
                date = datetime.strptime(date_str, "%Y-%m-%d")
                date_formatted = date.strftime("%Y-%m-%d %H:%M:%S")
                transaction_month = date.strftime("%Y-%m")
            except ValueError as e:
                flash(f"Invalid data in row for member {member_id}: {str(e)}")
                logger.error(f"Invalid data for member {member_id}: {str(e)}")
                continue

            if trans_type not in valid_types:
                flash(f"Invalid transaction type {trans_type} for member {member_id}")
                logger.error(f"Invalid transaction type {trans_type} for member {member_id}")
                continue
            if mode not in valid_modes:
                flash(f"Invalid transaction mode {mode} for member {member_id}")
                logger.error(f"Invalid transaction mode {mode} for member {member_id}")
                continue

            existing_transaction = None
            existing_index = None
            for idx, trans in enumerate(member_data["transactions"]):
                trans_date = datetime.strptime(trans["date"], "%Y-%m-%d %H:%M:%S")
                if trans["type"] == trans_type and trans_date.strftime("%Y-%m") == transaction_month:
                    existing_transaction = trans
                    existing_index = idx
                    break

            update_data = {}
            if existing_transaction:
                old_amount = existing_transaction["amount"]
                member_data["transactions"][existing_index] = {
                    "amount": amount,
                    "type": trans_type,
                    "mode": mode,
                    "transaction_id": transaction_id,
                    "date": date_formatted
                }
                update_data["transactions"] = member_data["transactions"]

                if trans_type == "Savings":
                    update_data["savings"] = member_data["savings"] - old_amount + amount
                elif trans_type == "Loan":
                    update_data["loan"] = member_data["loan"] - old_amount + amount
                    update_data["loan_date"] = date_formatted if amount > 0 else None
                elif trans_type == "Repayment":
                    if amount > member_data["loan"]:
                        flash(f"Repayment {amount} exceeds loan {member_data['loan']} for member {member_id}")
                        logger.warning(f"Repayment {amount} exceeds loan {member_data['loan']} for member {member_id}")
                        continue
                    update_data["loan"] = member_data["loan"] + old_amount - amount
                    if update_data["loan"] == 0:
                        update_data["loan_date"] = None

                result = members_collection.update_one({"_id": ObjectId(member_id)}, {"$set": update_data})
                if result.modified_count > 0:
                    updated_count += 1
                    logger.info(f"Updated transaction for member {member_id}: {trans_type}, month: {transaction_month}")
                else:
                    flash(f"Failed to update transaction for member {member_id}")
                    logger.error(f"Update failed for transaction for member {member_id}")
            else:
                transaction = {
                    "amount": amount,
                    "type": trans_type,
                    "mode": mode,
                    "transaction_id": transaction_id,
                    "date": date_formatted
                }
                update_data["transactions"] = member_data["transactions"] + [transaction]

                if trans_type == "Savings":
                    update_data["savings"] = member_data["savings"] + amount
                elif trans_type == "Loan":
                    update_data["loan"] = member_data["loan"] + amount
                    update_data["loan_date"] = date_formatted
                elif trans_type == "Repayment":
                    if amount > member_data["loan"]:
                        flash(f"Repayment {amount} exceeds loan {member_data['loan']} for member {member_id}")
                        logger.warning(f"Repayment {amount} exceeds loan {member_data['loan']} for member {member_id}")
                        continue
                    update_data["loan"] = member_data["loan"] - amount
                    if update_data["loan"] == 0:
                        update_data["loan_date"] = None

                result = members_collection.update_one({"_id": ObjectId(member_id)}, {"$set": update_data})
                if result.modified_count > 0:
                    imported_count += 1
                    logger.info(f"Imported transaction for member {member_id}: {transaction}")
                else:
                    flash(f"Failed to add transaction for member {member_id}")
                    logger.error(f"Add failed for transaction for member {member_id}")

        update_group_savings(group_id)
        flash(f"Successfully imported {imported_count} new transactions and updated {updated_count} existing transactions")
        logger.info(f"Imported {imported_count} new and updated {updated_count} existing transactions for group {group_id}")
    except Exception as e:
        flash(f"Error processing file: {str(e)}")
        logger.error(f"Error processing file {file.filename}: {str(e)}")
    return redirect(url_for("index", group_id=group_id))

@app.route("/delete_transaction/<member_id>/<int:transaction_index>", methods=["POST"])
@login_required
@admin_required
def delete_transaction(member_id, transaction_index):
    member_data = members_collection.find_one({"_id": ObjectId(member_id)})
    if not member_data:
        flash("Member not found")
        logger.error(f"Member not found: {member_id}")
        return redirect(url_for("index"))

    if transaction_index < 0 or transaction_index >= len(member_data["transactions"]):
        flash("Invalid transaction index")
        logger.error(f"Invalid transaction index: {transaction_index} for member {member_id}")
        return redirect(url_for("member_report", member_id=member_id))

    transaction = member_data["transactions"].pop(transaction_index)
    update_data = {"transactions": member_data["transactions"]}

    recalculated = recalculate_member_fields(member_data)
    update_data.update(recalculated)

    result = members_collection.update_one({"_id": ObjectId(member_id)}, {"$set": update_data})
    if result.modified_count > 0:
        flash(f"Transaction deleted: {transaction['type']} of ₹{transaction['amount']}")
        logger.info(f"Deleted transaction for member {member_id}: {transaction}")
        update_group_savings(member_data["group_id"])
    else:
        flash("Failed to delete transaction")
        logger.error(f"Failed to delete transaction for member {member_id}")

    return redirect(url_for("member_report", member_id=member_id))

@app.route("/edit_transaction/<member_id>/<int:transaction_index>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_transaction(member_id, transaction_index):
    member_data = members_collection.find_one({"_id": ObjectId(member_id)})
    if not member_data:
        flash("Member not found")
        logger.error(f"Member not found: {member_id}")
        return redirect(url_for("index"))

    if transaction_index < 0 or transaction_index >= len(member_data["transactions"]):
        flash("Invalid transaction index")
        logger.error(f"Invalid transaction index: {transaction_index} for member {member_id}")
        return redirect(url_for("member_report", member_id=member_id))

    transaction = member_data["transactions"][transaction_index]
    if request.method == "POST":
        try:
            amount = float(request.form["amount"])
            trans_type = request.form["type"]
            mode = request.form["mode"]
            transaction_id = request.form.get("transaction_id", "")
            date_str = request.form["date"]
            date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            flash(f"Invalid input: {str(e)}")
            logger.error(f"Invalid input for transaction edit: {str(e)}")
            return redirect(url_for("edit_transaction", member_id=member_id, transaction_index=transaction_index))

        valid_types = {"Savings", "Loan", "Repayment"}
        valid_modes = {"UPI", "CASH", "NEFT", "OTHER"}
        if trans_type not in valid_types:
            flash(f"Invalid transaction type: {trans_type}")
            logger.error(f"Invalid transaction type: {trans_type} for member {member_id}")
            return redirect(url_for("edit_transaction", member_id=member_id, transaction_index=transaction_index))
        if mode not in valid_modes:
            flash(f"Invalid transaction mode: {mode}")
            logger.error(f"Invalid transaction mode: {mode} for member {member_id}")
            return redirect(url_for("edit_transaction", member_id=member_id, transaction_index=transaction_index))

        old_transaction = transaction.copy()
        member_data["transactions"][transaction_index] = {
            "amount": amount,
            "type": trans_type,
            "mode": mode,
            "transaction_id": transaction_id,
            "date": date
        }
        update_data = {"transactions": member_data["transactions"]}

        recalculated = recalculate_member_fields(member_data)
        update_data.update(recalculated)

        if trans_type == "Repayment" and update_data["loan"] < 0:
            flash(f"Repayment {amount} exceeds loan balance")
            logger.warning(f"Repayment {amount} exceeds loan for member {member_id}")
            return redirect(url_for("edit_transaction", member_id=member_id, transaction_index=transaction_index))

        result = members_collection.update_one({"_id": ObjectId(member_id)}, {"$set": update_data})
        if result.modified_count > 0:
            flash("Transaction updated successfully")
            logger.info(f"Updated transaction for member {member_id}: from {old_transaction} to {update_data['transactions'][transaction_index]}")
            update_group_savings(member_data["group_id"])
        else:
            flash("Failed to update transaction")
            logger.error(f"Failed to update transaction for member {member_id}")

        return redirect(url_for("member_report", member_id=member_id))

    return render_template("edit_transaction.html", member=Member.from_dict(member_data), transaction=transaction, transaction_index=transaction_index)

@app.route("/set_interest", methods=["POST"])
@login_required
@admin_required
def set_interest():
    group_id = request.form["group_id"]
    interest_rate = float(request.form["rate"]) / 100
    groups_collection.update_one({"_id": ObjectId(group_id)}, {"$set": {"interest_rate": interest_rate}})
    return redirect(url_for("index", group_id=group_id))

@app.route("/report/<member_id>", methods=["GET"])
@login_required
def member_report(member_id):
    member_data = members_collection.find_one({"_id": ObjectId(member_id)})
    if not member_data:
        return "Member not found", 404
    member = Member.from_dict(member_data)
    group = groups_collection.find_one({"_id": ObjectId(member.group_id)})
    interest = member.loan * group["interest_rate"]
    monthly_repayment = member.calculate_monthly_repayment()
    return render_template("report.html", member=member, interest=interest, interest_rate=group["interest_rate"]*100, monthly_repayment=monthly_repayment, user_role=session.get("role"))

@app.route("/report_pdf/<member_id>", methods=["GET"])
@login_required
def member_report_pdf(member_id):
    member_data = members_collection.find_one({"_id": ObjectId(member_id)})
    if not member_data:
        return "Member not found", 404
    member = Member.from_dict(member_data)
    group = groups_collection.find_one({"_id": ObjectId(member.group_id)})

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Member Report: {member.name} (ID: {member.id[-4:]}) - Group: {group['name']}", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Email: {member.email}", styles["Normal"]))
    elements.append(Paragraph(f"Mobile: {member.mobile}", styles["Normal"]))
    elements.append(Paragraph(f"Savings: ₹{member.savings:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Loan: ₹{member.loan:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Annual Interest ({group['interest_rate']*100:.1f}%): ₹{member.loan * group['interest_rate']:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Monthly Repayment (12 months): ₹{member.calculate_monthly_repayment():.2f}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Transaction History", styles["Heading2"]))
    if member.transactions:
        data = [["Date", "Type", "Mode", "Transaction ID", "Amount"]]
        for t in member.transactions:
            data.append([t["date"], t["type"], t["mode"], t.get("transaction_id", ""), f"₹{t['amount']:.2f}"])
        table = Table(data, colWidths=[150, 80, 80, 100, 100])
        table.setStyle([("GRID", (0, 0), (-1, -1), 1, "black"), ("BACKGROUND", (0, 0), (-1, 0), "grey")])
        elements.append(table)
    else:
        elements.append(Paragraph("No transactions yet.", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"member_report_{member_id}.pdf", mimetype="application/pdf")

@app.route("/report/group/<group_id>", methods=["GET"])
@login_required
def group_report(group_id):
    update_group_savings(group_id)
    members = {str(m["_id"]): Member.from_dict(m) for m in members_collection.find({"group_id": ObjectId(group_id)})}
    group = groups_collection.find_one({"_id": ObjectId(group_id)})
    if not group:
        return "Group not found", 404
    total_savings = sum(m.savings for m in members.values()) + group["group_savings"]
    total_loans = sum(m.loan for m in members.values())
    total_interest = sum(m.loan * group["interest_rate"] for m in members.values())
    return render_template("group_report.html", members=members, group=group, total_savings=total_savings, total_loans=total_loans, total_interest=total_interest, user_role=session.get("role"))

@app.route("/report_pdf/group/<group_id>", methods=["GET"])
@login_required
def group_report_pdf(group_id):
    update_group_savings(group_id)
    members = {str(m["_id"]): Member.from_dict(m) for m in members_collection.find({"group_id": ObjectId(group_id)})}
    group = groups_collection.find_one({"_id": ObjectId(group_id)})
    if not group:
        return "Group not found", 404
    total_savings = sum(m.savings for m in members.values()) + group["group_savings"]
    total_loans = sum(m.loan for m in members.values())
    total_interest = sum(m.loan * group["interest_rate"] for m in members.values())

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Group Report: {group['name']}", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Address: {group['address']}", styles["Normal"]))
    elements.append(Paragraph(f"Total Members: {len(members)}", styles["Normal"]))
    elements.append(Paragraph(f"Total Savings (Individual): ₹{sum(m.savings for m in members.values()):.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Group Savings (Interest): ₹{group['group_savings']:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Total Combined Savings: ₹{total_savings:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Total Loans: ₹{total_loans:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Total Annual Interest ({group['interest_rate']*100:.1f}%): ₹{total_interest:.2f}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Member Summary", styles["Heading2"]))
    data = [["ID", "Name", "Savings", "Loan", "Monthly Repayment"]]
    for member in members.values():
        data.append([member.id[-4:], member.name, f"₹{member.savings:.2f}", f"₹{member.loan:.2f}", f"₹{member.calculate_monthly_repayment():.2f}"])
    table = Table(data, colWidths=[50, 200, 100, 100, 100])
    table.setStyle([("GRID", (0, 0), (-1, -1), 1, "black"), ("BACKGROUND", (0, 0), (-1, 0), "grey")])
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"group_report_{group_id}.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)