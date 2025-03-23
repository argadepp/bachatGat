from flask import Flask, request, render_template, redirect, url_for, jsonify, send_file
import os
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from PIL import Image
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# MongoDB connection
client = MongoClient("mongodb://mongodb:27017/")
db = client["bachat_gat_db"]
members_collection = db["members"]
groups_collection = db["groups"]

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

@app.route("/", methods=["GET"])
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
    return render_template("index.html", groups=groups, members=members, group=group, selected_group_id=selected_group_id)

@app.route("/create_group", methods=["POST"])
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
def add_member():
    group_id = request.form.get("group_id")
    name = request.form.get("name")
    email = request.form.get("email")
    mobile = request.form.get("mobile")
    photo = request.files.get("photo")

    # Check if group_id is valid and exists
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

@app.route("/edit_member/<member_id>", methods=["GET", "POST"])
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
def delete_member(member_id):
    member_data = members_collection.find_one({"_id": ObjectId(member_id)})
    if not member_data:
        return "Member not found", 404
    group_id = member_data["group_id"]
    members_collection.delete_one({"_id": ObjectId(member_id)})
    return redirect(url_for("index", group_id=group_id))

@app.route("/transaction", methods=["POST"])
def record_transaction():
    member_id = request.form["member_id"]
    amount = float(request.form["amount"])
    trans_type = request.form["type"]
    date_str = request.form["date"]
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD.", 400

    member_data = members_collection.find_one({"_id": ObjectId(member_id)})
    if not member_data:
        return "Member not found", 404

    transaction = {"amount": amount, "type": trans_type, "date": date}
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

@app.route("/set_interest", methods=["POST"])
def set_interest():
    group_id = request.form["group_id"]
    interest_rate = float(request.form["rate"]) / 100
    groups_collection.update_one({"_id": ObjectId(group_id)}, {"$set": {"interest_rate": interest_rate}})
    return redirect(url_for("index", group_id=group_id))

@app.route("/report/<member_id>", methods=["GET"])
def member_report(member_id):
    member_data = members_collection.find_one({"_id": ObjectId(member_id)})
    if not member_data:
        return "Member not found", 404
    member = Member.from_dict(member_data)
    group = groups_collection.find_one({"_id": ObjectId(member.group_id)})
    interest = member.loan * group["interest_rate"]
    monthly_repayment = member.calculate_monthly_repayment()
    return render_template("report.html", member=member, interest=interest, interest_rate=group["interest_rate"]*100, monthly_repayment=monthly_repayment)

@app.route("/report_pdf/<member_id>", methods=["GET"])
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
    elements.append(Paragraph(f"Savings: ${member.savings:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Loan: ${member.loan:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Annual Interest ({group['interest_rate']*100:.1f}%): ${member.loan * group['interest_rate']:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Monthly Repayment (12 months): ${member.calculate_monthly_repayment():.2f}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Transaction History", styles["Heading2"]))
    if member.transactions:
        data = [["Date", "Type", "Amount"]]
        for t in member.transactions:
            data.append([t["date"], t["type"], f"${t['amount']:.2f}"])
        table = Table(data, colWidths=[200, 100, 100])
        table.setStyle([("GRID", (0, 0), (-1, -1), 1, "black"), ("BACKGROUND", (0, 0), (-1, 0), "grey")])
        elements.append(table)
    else:
        elements.append(Paragraph("No transactions yet.", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"member_report_{member_id}.pdf", mimetype="application/pdf")

@app.route("/report/group/<group_id>", methods=["GET"])
def group_report(group_id):
    update_group_savings(group_id)
    members = {str(m["_id"]): Member.from_dict(m) for m in members_collection.find({"group_id": ObjectId(group_id)})}
    group = groups_collection.find_one({"_id": ObjectId(group_id)})
    if not group:
        return "Group not found", 404
    total_savings = sum(m.savings for m in members.values()) + group["group_savings"]
    total_loans = sum(m.loan for m in members.values())
    total_interest = sum(m.loan * group["interest_rate"] for m in members.values())
    return render_template("group_report.html", members=members, group=group, total_savings=total_savings, total_loans=total_loans, total_interest=total_interest)

@app.route("/report_pdf/group/<group_id>", methods=["GET"])
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
    elements.append(Paragraph(f"Total Savings (Individual): ${sum(m.savings for m in members.values()):.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Group Savings (Interest): ${group['group_savings']:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Total Combined Savings: ${total_savings:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Total Loans: ${total_loans:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Total Annual Interest ({group['interest_rate']*100:.1f}%): ${total_interest:.2f}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Member Summary", styles["Heading2"]))
    data = [["ID", "Name", "Savings", "Loan", "Monthly Repayment"]]
    for member in members.values():
        data.append([member.id[-4:], member.name, f"${member.savings:.2f}", f"${member.loan:.2f}", f"${member.calculate_monthly_repayment():.2f}"])
    table = Table(data, colWidths=[50, 200, 100, 100, 100])
    table.setStyle([("GRID", (0, 0), (-1, -1), 1, "black"), ("BACKGROUND", (0, 0), (-1, 0), "grey")])
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"group_report_{group_id}.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)