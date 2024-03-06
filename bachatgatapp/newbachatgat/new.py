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

def main():
    principal = float(input("Enter the loan amount: "))
    annual_interest_rate = float(input("Enter the annual interest rate (%): "))
    loan_term_in_years = int(input("Enter the loan term in years: "))

    amortization_schedule = calculate_monthly_amortization(principal, annual_interest_rate, loan_term_in_years)

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
