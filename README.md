# Bachatgat

![Bachatgat Logo](path/to/your/logo.png)

Bachatgat is a web application designed to simplify and manage group savings (bachat) within a community. It helps members of a group to contribute, track savings, and request loans efficiently.

## Features

- **User Registration:** Register your Bachatgat with details like name, member count, address, contact number, email, and password.

- **Login:** Log in securely to access your Bachatgat dashboard.

- **View Bachat:** Track the total savings for the entire group and individual members over different months.

- **Loan Requests:** Members can request loans, and once approved by the admin, the loan amount is deducted from the total savings.

- **Loan Details:** View details of loans, including interest rates, due amounts, and payment history.

- **Dashboard:** An admin dashboard to manage members, loan requests, and approve/reject requests.

## Technologies Used

- **Frontend:** HTML, CSS, Bootstrap
- **Backend:** Python, Flask (Web Framework)
- **Database:** MySQL
- **Deployment:** Docker, GitHub Actions

## Getting Started

1. Clone the repository:

    ```bash
    git clone https://github.com/your-username/bachatgat.git
    cd bachatgat
    ```

2. Set up the virtual environment:

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use venv\Scripts\activate
    ```

3. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Run the application:

    ```bash
    python app.py
    ```

5. Access the application at `http://localhost:5000` in your web browser.

## Contributing

We welcome contributions! Feel free to fork the repository, make changes, and submit a pull request to help improve Bachatgat.

## Screenshots

![Wecome Page 1](/auth-template/__screenshots/welcome.JPG)

![Register Page 2](/auth-template/__screenshots/register.JPG)

...

## License

This project is licensed under the [MIT License](LICENSE).
