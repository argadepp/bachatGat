from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import math
from prettytable import PrettyTable
from dateutil.relativedelta import relativedelta
from flask import flash
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal, getcontext

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bachatgat'

# MySQL Configuration
app.config['MYSQL_HOST'] = os.getenv('DB_HOST', 'vrushali.pratikargade.online')
app.config['MYSQL_USER'] = os.getenv('DB_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('DB_PASSWORD', 'password')
app.config['MYSQL_DB'] = os.getenv('DB_NAME', 'jansevadb')
app.config['MYSQL_PORT'] = 3307
mysql = MySQL(app)

# Home page
@app.route('/')
def home():
    return render_template('index.html')

def get_next_month():
    today = datetime.today()
    next_month = today + relativedelta(months=1)
    return next_month.date()
# Registration page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Handle registration form submission
        gat_name = request.form['gatName']
        member_count = request.form['memberCount']
        address = request.form['address']
        contact_number = request.form['contactNumber']
        email = request.form['email']
        password = generate_password_hash(request.form['password'], method='sha256')

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO gats (gat_name, member_count, address, contact_number, email, password_hash) VALUES (%s, %s, %s, %s, %s, %s)",
                    (gat_name, member_count, address, contact_number, email, password))
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('dashboard'))

    return render_template('register.html')
# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Handle login form submission
        gat_identifier = request.form['gatId']
        password = request.form['password']

        # Check if the gat_identifier is an email
        is_email = '@' in gat_identifier

        cur = mysql.connection.cursor()
        if is_email:
            cur.execute("SELECT gat_id, email, password_hash FROM gats WHERE email = %s", (gat_identifier,))
        else:
            cur.execute("SELECT gat_id, email, password_hash FROM gats WHERE gat_name = %s", (gat_identifier,))

        result = cur.fetchone()
        cur.close()

        if result and check_password_hash(result[2], password):  # Change here
            session['gat_id'] = result[0]  # Change here
            return redirect(url_for('dashboard'))
        else:
            return render_template('error.html', message='Invalid credentials')

    return render_template('login.html')
# Route to display the loan request form
# Loan request form page
@app.route('/loan_request_form/<int:member_id>', methods=['GET', 'POST'])
def loan_request_form(member_id):
    if 'gat_id' in session:
        gat_id = session['gat_id']  # Retrieve gat_id from the session
        cur = mysql.connection.cursor()

        if request.method == 'POST':
            # Handle loan request submission
            loan_amount = float(request.form['loanAmount'])
            loan_interest_rate = float(request.form['interestRate'])
            
            # Insert data into the 'loan_requests' table
            cur.execute("INSERT INTO loan_requests (gat_id, member_id, request_amount, interest_rate, request_date) VALUES (%s, %s, %s, %s, %s)",
                        (gat_id, member_id, loan_amount, loan_interest_rate, datetime.now()))
            mysql.connection.commit()

            return redirect(url_for('view_bachat'))

        # Retrieve member information for the loan request form
        cur.execute("SELECT * FROM members WHERE member_id = %s AND gat_id = %s", (member_id, gat_id))
        member = cur.fetchone()

        # Fetch the interest rate from the interest_rate table
        cur.execute("SELECT interest_rate FROM interest_rate WHERE gat_id = %s", (gat_id,))
        interest_rate = cur.fetchone()

        cur.close()
        return render_template('loan_request_form.html', member=member, interest_rate=interest_rate[0])
    else:
        return redirect(url_for('login'))

@app.route('/pay_loan/<int:loan_id>', methods=['POST'])
def pay_loan(loan_id):
    if 'gat_id' in session:
        cur = mysql.connection.cursor()

        # Retrieve loan details
        cur.execute("SELECT * FROM loans WHERE loan_id = %s", (loan_id,))
        loan_details = cur.fetchone()

        # Check if the loan status is 'pending'
        if loan_details[6] == 'pending':  # Assuming 'status' is the 7th column in the SELECT query
            # Update loan status to 'paid' and deduct the loan amount from the total bachat
            cur.execute("UPDATE loans SET status = 'paid' WHERE loan_id = %s", (loan_id,))
            cur.execute("UPDATE total_bachat SET total_bachat_amount = total_bachat_amount - %s WHERE gat_id = %s",
                        (loan_details[3], loan_details[1]))  # Assuming 'loan_amount' and 'gat_id' columns

            mysql.connection.commit()

        cur.close()
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))
    

@app.route('/pay_due/<int:loan_id>', methods=['POST'])
def pay_due(loan_id):
    if 'gat_id' in session:
        gat_id = session['gat_id']
        cur = mysql.connection.cursor()

        # Fetch loan details
        cur.execute("SELECT * FROM loans WHERE loan_id = %s", (loan_id,))
        loan_details = cur.fetchone()

        # Check if loan status is 'approved'
        if loan_details and loan_details['status'] == 'approved':
            # Calculate due amount with interest
            due_amount = calculate_due_payments(loan_details)

            # Deduct due amount from total bachat
            cur.execute("UPDATE total_bachat SET total_bachat_amount = total_bachat_amount - %s WHERE gat_id = %s", (due_amount, gat_id))

            # Deduct due amount from loan
            cur.execute("UPDATE loans SET loan_amount = loan_amount - %s WHERE loan_id = %s", (due_amount, loan_id))

            # Commit changes
            mysql.connection.commit()

            cur.close()
            return render_template('pay_due.html', loan_details=loan_details)
    
    return redirect(url_for('dashboard'))
    

# Add a new route for displaying all bachat entries
@app.route('/all_bachat_entries', methods=['GET'])
def all_bachat_entries():
    if 'gat_id' in session:
        gat_id = session['gat_id']
        cur = mysql.connection.cursor()

        # Retrieve all bachat entries for the current GAT
        cur.execute("SELECT members.member_name, monthly_bachat.bachat_date, monthly_bachat.bachat_amount, monthly_bachat.bachat_id "
                    "FROM monthly_bachat INNER JOIN members ON monthly_bachat.member_id = members.member_id "
                    "WHERE monthly_bachat.gat_id = %s", (gat_id,))
        all_bachat_entries = cur.fetchall()

        cur.close()

        return render_template('all_bachat_entries.html', all_bachat_entries=all_bachat_entries)
    else:
        return redirect(url_for('login'))


# Edit bachat entry route
@app.route('/edit_bachat_entry/<int:entry_id>', methods=['GET', 'POST'])
def edit_bachat_entry(entry_id):
    if 'gat_id' in session:
        if request.method == 'POST':
            # Handle the form submission to update the bachat entry
            new_bachat_amount = request.form['newBachatAmount']

            cur = mysql.connection.cursor()
            cur.execute("UPDATE monthly_bachat SET bachat_amount = %s WHERE entry_id = %s", (new_bachat_amount, entry_id))
            mysql.connection.commit()
            cur.close()

            return redirect(url_for('all_bachat_entries'))

        # Retrieve the existing entry details for editing
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM monthly_bachat WHERE bachat_id = %s", (entry_id,))
        entry_details = cur.fetchone()
        cur.close()

        return render_template('edit_bachat_entry.html', entry_details=entry_details)
    else:
        return redirect(url_for('login'))

# Delete bachat entry route
@app.route('/delete_bachat_entry/<int:entry_id>', methods=['GET', 'POST'])
def delete_bachat_entry(entry_id):
    if 'gat_id' in session:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM monthly_bachat WHERE bachat_id = %s", (entry_id,))
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('all_bachat_entries'))
    else:
        return redirect(url_for('login'))
# Add a new route for pending bachat shares
@app.route('/pending_bachat_shares', methods=['GET'])
def pending_bachat_shares():
    if 'gat_id' in session:
        gat_id = session['gat_id']
        cur = mysql.connection.cursor()

        # Retrieve members who have not paid the bachat share for the current month
        cur.execute("SELECT members.member_name, members.member_id "
            "FROM members LEFT JOIN monthly_bachat "
            "ON members.member_id = monthly_bachat.member_id "
            "AND MONTH(monthly_bachat.bachat_date) = MONTH(CURDATE()) "
            "WHERE members.gat_id = %s AND (monthly_bachat.bachat_date IS NULL)",
            (gat_id,))
        pending_members = cur.fetchall()

        cur.close()
        
        return render_template('pending_bachat_shares.html', pending_members=pending_members)
    else:
        return redirect(url_for('login'))

# Dashboard page (requires login)
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'gat_id' in session:
        gat_id = session['gat_id']
        cur = mysql.connection.cursor()

        # Retrieve members
        cur.execute("SELECT * FROM members WHERE gat_id = %s", (gat_id,))
        members = cur.fetchall()

        monthly_bachat_current_month = []
        cur.execute("SELECT members.member_name, monthly_bachat.bachat_amount "
                    "FROM members LEFT JOIN monthly_bachat "
                    "ON members.member_id = monthly_bachat.member_id "
                    "AND MONTH(monthly_bachat.bachat_date) = MONTH(CURDATE()) "
                    "WHERE members.gat_id = %s", (gat_id,))
        monthly_bachat_current_month = cur.fetchall()
        # Fetch loan requests as dictionaries
        cur.execute("SELECT * FROM loan_requests WHERE gat_id = %s", (gat_id,))
        loan_requests = cur.fetchall()
        columns = [column[0] for column in cur.description]  # Fetch column names
        
        loan_requests = [dict(zip(columns, row)) for row in loan_requests] 

        

        if request.method == 'POST':
            if 'delete_member' in request.form:
                # Handle deleting a member
                member_id_to_delete = request.form['delete_member']
                cur.execute("DELETE FROM members WHERE member_id = %s AND gat_id = %s", (member_id_to_delete, gat_id))
                mysql.connection.commit()

            elif 'add_bachat' in request.form:
                # Redirect to the add_bachat page
                return redirect(url_for('add_bachat'))
            elif 'add_member' in request.form:
                # Redirect to the add_bachat page
                return redirect(url_for('add_members'))
            elif 'view_bachat' in request.form:
                # Redirect to the view_bachat page
                return redirect(url_for('view_bachat'))
            elif 'request_loan' in request.form:
                # Redirect to the loan_request_form page
                member_id = request.form['request_loan']
                return redirect(url_for('loan_request_form', member_id=member_id))
            

            # Handle adding a new member (existing code)
            member_name = request.form['memberName']
            member_email = request.form['memberEmail']
            member_password = generate_password_hash(request.form['memberPassword'], method='sha256')
            member_address = request.form['memberAddress']
            member_mobile = request.form['memberMobile']
            member_type = request.form['memberType']

            # Insert data into the 'members' table
            cur.execute("INSERT INTO members (gat_id, member_name, member_email, member_password, member_address, member_mobile, member_type) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (gat_id, member_name, member_email, member_password, member_address, member_mobile, member_type))
            mysql.connection.commit()

            return redirect(url_for('dashboard'))

        cur.close()
        return render_template('dashboard.html', members=members, loan_requests=loan_requests)
    else:
        return redirect(url_for('login'))
    
# Add Members page
@app.route('/add_members', methods=['GET', 'POST'])
def add_members():
    if 'gat_id' in session:
        if request.method == 'POST':
            # Handle adding a new member (existing code)
            member_name = request.form['memberName']
            member_email = request.form['memberEmail']
            member_password = generate_password_hash(request.form['memberPassword'], method='sha256')
            member_address = request.form['memberAddress']
            member_mobile = request.form['memberMobile']
            member_type = request.form['memberType']

            gat_id = session['gat_id']
            
            cur = mysql.connection.cursor()
            # Insert data into the 'members' table
            cur.execute("INSERT INTO members (gat_id, member_name, member_email, member_password, member_address, member_mobile, member_type) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (gat_id, member_name, member_email, member_password, member_address, member_mobile, member_type))
            mysql.connection.commit()
            cur.close()

            return redirect(url_for('dashboard'))

        return render_template('add_members.html')
    else:
        return redirect(url_for('login'))
# Add a new route to update the loan status
@app.route('/update_loan_status/<int:loan_request_id>', methods=['POST'])
def update_loan_status(loan_request_id):
    if 'gat_id' in session:
        cur = mysql.connection.cursor()

        # Update loan request status to approved
        cur.execute("UPDATE loan_requests SET request_status = 'approved' WHERE request_id = %s", (loan_request_id,))
        mysql.connection.commit()

        cur.close()
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))



def approve_loan(loan_request_id):
    if 'gat_id' in session:
        cur = mysql.connection.cursor()

        # Retrieve loan request details
        cur.execute("SELECT * FROM loan_requests WHERE request_id = %s", (loan_request_id,))
        loan_request = cur.fetchone()

        cur.close()

        # Render the loan_details.html template with loan_request details
        return render_template('loan_details.html', loan_request=loan_request)
    else:
        return redirect(url_for('login'))




def get_loan_request_by_id(request_id):
    cur = mysql.connection.cursor()

    # Execute SQL query to fetch loan request by ID
    cur.execute("SELECT * FROM loan_requests WHERE request_id = %s", (request_id,))
    loan_request = cur.fetchone()

    cur.close()
    return loan_request
@app.route('/approve_loan_request/<int:request_id>', methods=['POST'])
def approve_loan_request(request_id):
    if 'gat_id' in session:
        cur = mysql.connection.cursor()

        # Retrieve loan request details
        cur.execute("SELECT * FROM loan_requests WHERE request_id = %s", (request_id,))
        loan_request = cur.fetchone()

        # Check if the loan status is 'approved'
        if loan_request[5] == 'approved':  # Assuming 'request_status' is the 6th column in the SELECT query
            # Deduct the approved amount from the total bachat
            cur.execute("UPDATE total_bachat SET total_bachat_amount = total_bachat_amount - %s WHERE gat_id = %s",
                        (loan_request[3], loan_request[1]))  # Assuming 'request_amount' and 'gat_id' columns

            # Insert loan details into the 'loans' table
            cur.execute("INSERT INTO loans (gat_id, member_id, loan_amount, interest_rate, request_id, due_date) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (loan_request[1], loan_request[2], loan_request[3], loan_request[4], loan_request[0], get_next_month()))
            mysql.connection.commit()

        # Update loan request status to approved
        cur.execute("UPDATE loan_requests SET request_status = 'approved' WHERE request_id = %s", (request_id,))
        mysql.connection.commit()

        cur.close()
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

# Method to calculate EMI
def calculate_emi(principal, annual_interest_rate, loan_term_in_years):
    # Convert principal and annual_interest_rate to Decimal if not already
    principal = Decimal(str(principal))
    annual_interest_rate = Decimal(str(annual_interest_rate))

    monthly_interest_rate = annual_interest_rate / 12 / 100
    total_payments = loan_term_in_years * 12

    emi = (principal * monthly_interest_rate) / (1 - (1 + monthly_interest_rate) ** -total_payments)

    amortization_schedule = []

    remaining_balance = principal

    for month in range(1, total_payments + 1):
        interest_payment = remaining_balance * monthly_interest_rate
        principal_payment = emi - interest_payment
        remaining_balance -= principal_payment

        amortization_schedule.append({
            "Month": month,
            "Monthly_Payment": emi,
            "Principal_Repayment": principal_payment,
            "Interest_Payment": interest_payment,
            "Remaining_Balance": remaining_balance
        })

    return amortization_schedule

def display_amortization_schedule(amortization_schedule):
    table = PrettyTable()
    table.field_names = ["Month", "Monthly Payment", "Principal Repayment", "Interest Payment", "Remaining Balance"]

    for payment in amortization_schedule:
        table.add_row([
            payment["Month"],
            "{:.2f}".format(payment["Monthly_Payment"]),
            "{:.2f}".format(payment["Principal_Repayment"]),
            "{:.2f}".format(payment["Interest_Payment"]),
            "{:.2f}".format(payment["Remaining_Balance"])
        ])

    return table.get_html_string()

def fetch_loan_details_from_database(loan_id):
    try:
        # connection = mysql.connector.connect(**db_config)
        cursor = mysql.connection.cursor()

        # Assuming your loans table has columns like 'loan_amount', 'interest_rate', 'due_date', 'status', etc.
        query = "SELECT * FROM loans WHERE loan_id = %s"
        cursor.execute(query, (loan_id,))
        loan_details = cursor.fetchone()

        return loan_details

    except Exception as e:
        print(f"Error fetching loan details: {e}")
        return None

    finally:
        cursor.close()

def get_remaining_months(due_date):
    # Replace this with your actual logic to calculate remaining months
    # Example: (replace this with your actual logic)
    from datetime import datetime

    today = datetime.now()
    due_date = datetime.strptime(due_date, '%Y-%m-%d')

    remaining_months = (due_date.year - today.year) * 12 + due_date.month - today.month

    return remaining_months




@app.route('/loan_details/<int:request_id>', methods=['GET', 'POST'])
def loan_details(request_id):
    if 'gat_id' in session:
        gat_id = session['gat_id']
        cur = mysql.connection.cursor()
        loan_request = get_loan_request_by_id(request_id)

        
        if request.method == 'POST':
            # Handle loan approval submission
            approved = request.form.get('approve_loan')
            if approved:
                # Update the loan request status to approved
                cur.execute("UPDATE loan_requests SET request_status = 'approved' WHERE request_id = %s", (request_id,))
                mysql.connection.commit()

                # Implement logic to deduct amount and charge interest, update monthly payment, etc.

                flash("Loan request approved successfully!", 'success')
                return redirect(url_for('view_bachat'))

        # Fetch loan details, member details, and interest rate
        cur.execute("SELECT loan_requests.*, members.member_name FROM loan_requests "
                    "JOIN members ON loan_requests.member_id = members.member_id "
                    "WHERE loan_requests.gat_id = %s AND loan_requests.request_id = %s", (gat_id, request_id))
        loan_details = cur.fetchone()
        
        cur.close()
        return render_template('loan_details.html', loan_details=loan_details)
    else:
        return redirect(url_for('login'))
@app.errorhandler(Exception)
def handle_error(e):
    print(f"An error occurred: {e}")
    return "An error occurred", 500


def display_amortization_schedule(amortization_schedule):
    table_html = """
    <table class="table table-bordered">
        <thead>
            <tr>
                <th>Month</th>
                <th>Monthly Payment</th>
                <th>Principal Repayment</th>
                <th>Interest Payment</th>
                <th>Remaining Balance</th>
            </tr>
        </thead>
        <tbody>
    """

    for payment in amortization_schedule:
        table_html += f"""
            <tr>
                <td>{payment['Month']}</td>
                <td>{payment['Monthly_Payment']:.2f}</td>
                <td>{payment['Principal_Repayment']:.2f}</td>
                <td>{payment['Interest_Payment']:.2f}</td>
                <td>{payment['Remaining_Balance']:.2f}</td>
            </tr>
        """

    table_html += """
        </tbody>
    </table>
    """

    return table_html

def calculate_monthly_amortization(principal, annual_interest_rate, loan_term_in_years):
    # Set precision for Decimal calculations
    getcontext().prec = 28  # Adjust precision as needed

    principal = Decimal(str(principal))
    annual_interest_rate = Decimal(str(annual_interest_rate))

    monthly_interest_rate = annual_interest_rate / 12 / 100
    total_payments = loan_term_in_years * 12

    emi = (principal * monthly_interest_rate) / (1 - (1 + monthly_interest_rate) ** -total_payments)

    amortization_schedule = []

    remaining_balance = principal

    for month in range(1, total_payments + 1):
        interest_payment = remaining_balance * monthly_interest_rate
        principal_payment = emi - interest_payment
        remaining_balance -= principal_payment

        amortization_schedule.append({
            "Month": month,
            "Monthly_Payment": emi,
            "Principal_Repayment": principal_payment,
            "Interest_Payment": interest_payment,
            "Remaining_Balance": remaining_balance
        })

    return amortization_schedule

@app.route('/calculate_emi_route/<int:loan_id>', methods=['GET', 'POST'])
def calculate_emi_route(loan_id):
    if request.method == 'POST':
        # Handle the form submission if needed
        pass

    cur = mysql.connection.cursor()
    cur.execute("SELECT lr.*, m.member_name FROM loan_requests lr JOIN members m ON lr.member_id = m.member_id WHERE lr.request_id = %s", (loan_id,))
    loan_details = cur.fetchone()
    cur.close()

    if loan_details:
        principal = loan_details[3]
        principal = Decimal(str(principal))
        annual_rate = loan_details[4]
        member_name = loan_details[-1]
        emi_schedule = calculate_monthly_amortization(principal, annual_rate, 1)
        table_html = display_amortization_schedule(emi_schedule)

        return render_template('calculate_emi.html', table_html=table_html, loan_details=loan_details)
    else:
        return render_template('error.html', message="Loan not found")
    
    

@app.route('/make_due_payment/<int:loan_request_id>/<int:month>')
def make_due_payment(loan_request_id, month):
    if 'gat_id' in session:
        cur = mysql.connection.cursor()

        # Retrieve loan request details
        cur.execute("SELECT * FROM loan_requests WHERE loan_request_id = %s", (loan_request_id,))
        loan_request = cur.fetchone()

        # Deduct the due payment from the total
        cur.execute("UPDATE gat SET total_bachat = total_bachat - %s WHERE gat_id = %s", (due_payment_amount, loan_request['gat_id']))

        # Update due payment status
        cur.execute("UPDATE due_payments SET status = 'paid' WHERE loan_request_id = %s AND month = %s", (loan_request_id, month))
        mysql.connection.commit()

        cur.close()
        return redirect(url_for('due_payments', loan_request_id=loan_request_id))
    else:
        return redirect(url_for('login'))
    

# Flask route for changing loan status
@app.route('/change_loan_status/<int:request_id>', methods=['POST'])
def change_loan_status(request_id):
    if 'gat_id' in session:
        cur = mysql.connection.cursor()
        
        # Retrieve the new status from the form
        new_status = request.form['newStatus']

        # Update loan request status
        cur.execute("UPDATE loan_requests SET request_status = %s WHERE request_id = %s", (new_status, request_id))
        mysql.connection.commit()
        # approve_loan_request(request_id)
        cur.close()
        return redirect(url_for('loan_details', request_id=request_id))
    else:
        return redirect(url_for('login'))
@app.route('/update_total_bachat', methods=['POST'])
def update_total_bachat():
    if 'gat_id' in session:
        gat_id = session['gat_id']
        cur = mysql.connection.cursor()

        # Get the current month and year
        current_month_year = datetime.now().strftime("%Y-%m-01")

        # Calculate the total bachat for all previous months up to the current month
        month_start = datetime.strptime("2022-01-01", "%Y-%m-%d")  # Change this to the start month of your application
        while month_start <= datetime.now():
            month_end = month_start + relativedelta(months=1) - timedelta(days=1)

            cur.execute("SELECT SUM(bachat_amount) FROM monthly_bachat WHERE gat_id = %s AND "
                        "bachat_date BETWEEN %s AND %s", (gat_id, month_start, month_end))

            total_bachat_for_month = cur.fetchone()[0]

            # Check if there is an entry for the current month in total_bachat
            cur.execute("SELECT * FROM total_bachat WHERE gat_id = %s AND month_year = %s", (gat_id, month_start.strftime("%Y-%m-01")))
            existing_entry = cur.fetchone()

            if existing_entry:
                # Update the existing entry
                cur.execute("UPDATE total_bachat SET total_bachat_amount = %s WHERE gat_id = %s AND month_year = %s",
                            (total_bachat_for_month, gat_id, month_start.strftime("%Y-%m-01")))
            else:
                # Insert a new entry for the current month
                cur.execute("INSERT INTO total_bachat (gat_id, total_bachat_amount, month_year) VALUES (%s, %s, %s)",
                            (gat_id, total_bachat_for_month, month_start.strftime("%Y-%m-01")))

            month_start += relativedelta(months=1)

        mysql.connection.commit()
        cur.close()

        # Redirect to the page where you want to go after updating total_bachat
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))
# View Bachat page
@app.route('/view_bachat')
def view_bachat():
    if 'gat_id' in session:
        gat_id = session['gat_id']
        cur = mysql.connection.cursor()
        update_total_bachat()
        # Retrieve total bachat for all months for each member
        cur.execute("SELECT members.member_name, SUM(monthly_bachat.bachat_amount) "
                    "FROM members LEFT JOIN monthly_bachat "
                    "ON members.member_id = monthly_bachat.member_id "
                    "WHERE members.gat_id = %s "
                    "GROUP BY members.member_name", (gat_id,))
        total_bachat_all_months = cur.fetchall()

        cur.close()


        cur = mysql.connection.cursor()

        # Retrieve total bachat for the gat (group)
        cur.execute("SELECT SUM(total_bachat_amount) FROM total_bachat WHERE gat_id = %s", (gat_id,))
        total_bachat_for_gat_tuple = cur.fetchone()

        if total_bachat_for_gat_tuple and total_bachat_for_gat_tuple[0] is not None:
            total_bachat_for_gat = Decimal(total_bachat_for_gat_tuple[0])
        else:
            total_bachat_for_gat = Decimal(0)
        
        cur = mysql.connection.cursor()

        cur.execute("SELECT SUM(request_amount) FROM loan_requests WHERE request_status='approved'")
        loan_request_result = cur.fetchone()
        
        if loan_request_result and len(loan_request_result) > 0:
            loan_request = Decimal(loan_request_result[0])
        else:
            loan_request = Decimal(0)
        cur.close()
        # if loan_request[5] == 'approved':
        total_bachat_for_gat = total_bachat_for_gat - loan_request
        
        # else:
            #  total_bachat_for_gat=total_bachat_for_gat   


        cur.close()        
        return render_template('view_bachat.html', total_bachat_all_months=total_bachat_all_months, total_bachat_for_gat=total_bachat_for_gat , loan_request=loan_request )
    else:
        return redirect(url_for('login'))


# Logout route
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

# Edit Member page
@app.route('/edit_member/<int:member_id>', methods=['GET', 'POST'])
def edit_member(member_id):
    if 'gat_id' in session:
        gat_id = session['gat_id']
        cur = mysql.connection.cursor()

        # Retrieve member details for editing
        cur.execute("SELECT * FROM members WHERE member_id = %s AND gat_id = %s", (member_id, gat_id))
        member = cur.fetchone()

        if request.method == 'POST':
            # Handle updating member details
            member_name = request.form['memberName']
            member_email = request.form['memberEmail']
            member_password = generate_password_hash(request.form['memberPassword'], method='sha256')
            member_address = request.form['memberAddress']
            member_mobile = request.form['memberMobile']
            member_type = request.form['memberType']

            # Update data in the 'members' table
            cur.execute("UPDATE members SET member_name=%s, member_email=%s, member_password=%s, member_address=%s, member_mobile=%s, member_type=%s WHERE member_id=%s AND gat_id=%s",
                        (member_name, member_email, member_password, member_address, member_mobile, member_type, member_id, gat_id))
            mysql.connection.commit()

            return redirect(url_for('dashboard'))
    
        cur.close()
        return render_template('edit_member.html', member=member)
        
    else:
        return redirect(url_for('login'))

# Delete Member route
@app.route('/delete_member/<int:member_id>', methods=['GET'])
def delete_member(member_id):
    if 'gat_id' in session:
        gat_id = session['gat_id']
        cur = mysql.connection.cursor()

        # Check if the member belongs to the gat
        cur.execute("SELECT 1 FROM members WHERE member_id = %s AND gat_id = %s", (member_id, gat_id))
        result = cur.fetchone()

        if result:
            # Delete the member
            cur.execute("DELETE FROM members WHERE member_id = %s AND gat_id = %s", (member_id, gat_id))
            mysql.connection.commit()

        cur.close()
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

@app.route('/set_interest_rate', methods=['GET', 'POST'])
def set_interest_rate():
    if 'gat_id' in session:
        gat_id = session['gat_id']
        cur = mysql.connection.cursor()

        if request.method == 'POST':
            interest_rate = request.form['interestRate']
            start_date = request.form['startDate']

            # Insert data into the 'interest_rate' table
            cur.execute("INSERT INTO interest_rate (gat_id, interest_rate, start_date) VALUES (%s, %s, %s)",
                        (gat_id, interest_rate, start_date))
            mysql.connection.commit()

            flash("Interest rate set successfully", 'success')
            return redirect(url_for('dashboard'))

        cur.close()
        return render_template('set_interest_rate.html')
    else:
        return redirect(url_for('login'))
    
@app.route('/pay_now', methods=['POST'])
def pay_now():
    # Your logic for processing the payment or any other action
    # Redirect to the add_bachat page for now
    return redirect(url_for('add_bachat'))
# Add Bachat page
@app.route('/add_bachat', methods=['GET', 'POST'])
def add_bachat():
    if 'gat_id' in session:
        gat_id = session['gat_id']
        cur = mysql.connection.cursor()

        # Retrieve members for dropdown
        cur.execute("SELECT member_id, member_name FROM members WHERE gat_id = %s", (gat_id,))
        members = cur.fetchall()

        if request.method == 'POST':
          # Check if 'memberId' is present in the form data
          if 'memberId' in request.form:
              selected_member_id = request.form['memberId']
              selected_member_name = next((member[1] for member in members if member[0] == selected_member_id), None)
      
              # Check if 'bachatDate' is present in the form data
              bachat_date = request.form.get('bachatDate')
              if not bachat_date:
                  flash("Bachat Date is required", 'danger')
                  return redirect(url_for('add_bachat'))
      
              # Check if 'bachatAmount' is present in the form data
              bachat_amount = request.form.get('bachatAmount')
              if not bachat_amount:
                  flash("Bachat Amount is required", 'danger')
                  return redirect(url_for('add_bachat'))
      
              # Insert data into the 'monthly_bachat' table for regular addition
              cur.execute("INSERT INTO monthly_bachat (gat_id, member_id, bachat_date, bachat_amount) VALUES (%s, %s, %s, %s)",
                          (gat_id, selected_member_id, bachat_date, bachat_amount))
              mysql.connection.commit()
      
              flash(f"Bachat successfully added for member {selected_member_name} with ID {selected_member_id}", 'success')
              return redirect(url_for('dashboard', selected_member=selected_member_name))
      
          else:
              flash("Member ID is required", 'danger')
              return redirect(url_for('add_bachat'))


        cur.close()
        return render_template('add_bachat.html', members=members)
    else:
        return redirect(url_for('login'))

# Error page
@app.route('/error')
def error():
    message = request.args.get('message', 'An error occurred.')
    return render_template('error.html', message=message)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
