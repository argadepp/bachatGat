from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from flask import flash
app = Flask(__name__)
app.config['SECRET_KEY'] = 'bachatgat'

# MySQL Configuration
app.config['MYSQL_HOST'] = os.getenv('DB_HOST', 'database')
app.config['MYSQL_USER'] = os.getenv('DB_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('DB_PASSWORD', 'password')
app.config['MYSQL_DB'] = os.getenv('DB_NAME', 'jansevadb')

mysql = MySQL(app)

# Home page
@app.route('/')
def home():
    return render_template('index.html')

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
        # Check if the request is a POST request
        if request.method == 'POST':
            gat_id = session['gat_id']
            cur = mysql.connection.cursor()

            # Retrieve the loan request data
            loan_request = get_loan_request_by_id(request_id)

            # Check if the loan request exists
            if loan_request is not None and loan_request['gat_id'] == gat_id:
                # Update the loan request status to 'Approved'
                cur.execute("UPDATE loan_requests SET request_status = %s WHERE request_id = %s", ('Approved', request_id))
                mysql.connection.commit()

                # Implement logic to deduct the amount from the total and charge interest
                # This could involve updating the member's account, calculating interest, etc.

                # Redirect to the loan details page after approval
                return redirect(url_for('loan_details', request_id=request_id))
            else:
                flash("Loan request not found or unauthorized", 'error')

            cur.close()
            return redirect(url_for('view_bachat'))
        else:
            # Handle case where the request is not a POST request
            flash("Invalid request method", 'error')
            return redirect(url_for('view_bachat'))
    else:
        # Redirect to login if the user is not logged in
        return redirect(url_for('login'))

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

@app.route('/due_payments/<int:loan_request_id>')
def due_payments(loan_request_id):
    if 'gat_id' in session:
        cur = mysql.connection.cursor()

        # Retrieve loan request details
        cur.execute("SELECT * FROM loan_requests WHERE loan_request_id = %s", (loan_request_id,))
        loan_request = cur.fetchone()

        # Calculate due payments
        due_payments = calculate_due_payments(loan_request)

        cur.close()
        return render_template('due_payments.html', loan_request=loan_request, due_payments=due_payments)
    else:
        return redirect(url_for('login'))
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

# ...

# View Bachat page
@app.route('/view_bachat')
def view_bachat():
    if 'gat_id' in session:
        gat_id = session['gat_id']
        cur = mysql.connection.cursor()

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
        cur.execute("SELECT SUM(monthly_bachat.bachat_amount) "
                    "FROM members LEFT JOIN monthly_bachat "
                    "ON members.member_id = monthly_bachat.member_id "
                    "WHERE members.gat_id = %s", (gat_id,))
        total_bachat_for_gat = cur.fetchone()[0]

        cur.close()        
        return render_template('view_bachat.html', total_bachat_all_months=total_bachat_all_months, total_bachat_for_gat=total_bachat_for_gat)
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
