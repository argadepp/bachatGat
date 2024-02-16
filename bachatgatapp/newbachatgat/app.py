from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'password'
app.config['MYSQL_DB'] = 'jansevadb'

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

        cur.close()
        return render_template('loan_request_form.html', member=member)
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
@app.route('/approve_loan/<int:request_id>', methods=['POST'])
def approve_loan(loan_request_id):
    if 'gat_id' in session:
        cur = mysql.connection.cursor()

        # Retrieve loan request details
        cur.execute("SELECT * FROM loan_requests WHERE request_id = %s", (loan_request_id,))
        loan_request = cur.fetchone()

        # Deduct the approved amount from the total
        cur.execute("UPDATE gat SET total_bachat = total_bachat - %s WHERE gat_id = %s", (loan_request['loan_amount'], loan_request['gat_id']))

        # Update loan request status to approved
        cur.execute("UPDATE loan_requests SET status = 'approved' WHERE request_id = %s", (loan_request_id,))
        mysql.connection.commit()

        cur.close()
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))
    
@app.route('/loan_details/<int:loan_request_id>')
def loan_details(loan_request_id):
    if 'gat_id' in session:
        cur = mysql.connection.cursor()

        # Retrieve loan request details
        cur.execute("SELECT * FROM loan_requests WHERE request_id = %s", (loan_request_id,))
        loan_request = cur.fetchone()

        cur.close()
        return render_template('loan_details.html', loan_request=loan_request)
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
            # Handle adding monthly bachat
            selected_member_id = request.form['memberId']
            bachat_date = request.form['bachatDate']
            bachat_amount = request.form['bachatAmount']

            # Insert data into the 'monthly_bachat' table
            cur.execute("INSERT INTO monthly_bachat (gat_id, member_id, bachat_date, bachat_amount) VALUES (%s, %s, %s, %s)",
                        (gat_id, selected_member_id, bachat_date, bachat_amount))
            mysql.connection.commit()

            return redirect(url_for('dashboard'))

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
