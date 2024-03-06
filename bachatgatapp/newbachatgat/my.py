from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import math
from dateutil.relativedelta import relativedelta
from flask import flash
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
app = Flask(__name__)
app.config['SECRET_KEY'] = 'bachatgat'
mysql = MySQL(app)

def calculate_monthly_amortization(principal, annual_interest_rate, loan_term_in_years):
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

def fetch_loan_data_from_db():
    # Modify these database connection details accordingly
    db_config = {
        "host": "vrushali.pratikargade.online",
        "user": "root",
        "password": "password",
        "database": "jansevadb",
        "port": 3307
    }

    # Establish a connection to the database
    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM loans WHERE loan_id = %s", (loan_id,))
    mysql.connection.commit()
    cur.close()

    # # Assuming you have a table named 'loans' with the necessary columns
    # query = "SELECT principal, annual_interest_rate, loan_term_in_years FROM loans LIMIT 1"

    # cursor.execute(query)
    loan_data = cursor.fetchone()

    cursor.close()
    connection.close()

    return loan_data

def main():
    loan_data = fetch_loan_data_from_db()

    if not loan_data:
        print("No loan data found in the database.")
        return

    principal = loan_data["principal"]
    # annual_interest_rate = loan_data["annual_interest_rate"]
    # loan_term_in_years = loan_data["loan_term_in_years"]

    amortization_schedule = calculate_monthly_amortization(principal)

    print("\nAmortization Schedule:")
    print("{:<10} {:<15} {:<20} {:<20} {:<20}".format(
        "Month", "Monthly Payment", "Principal Repayment", "Interest Payment", "Remaining Balance"
    ))

    for payment in amortization_schedule:
        print("{:<10} {:<15.2f} {:<20.2f} {:<20.2f} {:<20.2f}".format(
            payment["Month"],
            payment["Monthly_Payment"],
            payment["Principal_Repayment"],
            payment["Interest_Payment"],
            payment["Remaining_Balance"]
        ))

if __name__ == "__main__":
    main()
