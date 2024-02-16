from flask import Flask, render_template, request
import os

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/create-gat', methods=['POST'])
def create_gat():
    gat_name = request.form['gatName']
    email = request.form['email']
    password = request.form['password']
    icon = request.files['icon']

    # Save the uploaded image
    icon.save(os.path.join('uploads', icon.filename))

    # TODO: Send the form data to your Node.js backend API (e.g., using requests library)

    return 'BachatGat creation request sent successfully'


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
