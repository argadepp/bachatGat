const express = require('express');
const multer = require('multer');
const bodyParser = require('body-parser');
const mysql = require('mysql2');

const app = express();
const port = 3000;

const db = mysql.createConnection({
    host: 'localhost',
    user: 'root',
    password: 'password',
    database: 'bachatgat'
});

db.connect((err) => {
    if (err) {
        console.error('Database connection failed:', err);
    } else {
        console.log('Connected to the database');
    }
});

app.use(bodyParser.json());

app.use(bodyParser.json());

// Set up multer for file uploads
const storage = multer.memoryStorage();
const upload = multer({ storage: storage });

// Serve uploaded images
app.use('/uploads', express.static('uploads'));

// Create table query
const createTableQuery = `
    CREATE TABLE IF NOT EXISTS bachatgats (
        gatId INT PRIMARY KEY AUTO_INCREMENT,
        gatName VARCHAR(255) NOT NULL,
        email VARCHAR(255) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL,
        icon BLOB
    );
`;

// Execute create table query
db.query(createTableQuery, (err, results) => {
    if (err) {
        console.error('Error creating table:', err);
    } else {
        console.log('Table created successfully');
    }
});

// API endpoint to create a BachatGat
app.post('/create-gat', upload.single('icon'), (req, res) => {
    const { gatName, email, password } = req.body;
    const icon = req.file.buffer; // Uploaded image in binary form

    const insertQuery = 'INSERT INTO bachatgats (gatName, email, password, icon) VALUES (?, ?, ?, ?)';
    const values = [gatName, email, password, icon];

    db.query(insertQuery, values, (err, results) => {
        if (err) {
            console.error('Error creating BachatGat:', err);
            res.status(500).send('Internal Server Error');
        } else {
            console.log('BachatGat created successfully');
            res.status(200).send('BachatGat created successfully');
        }
    });
});

app.listen(port, () => {
    console.log(`Server is running on http://localhost:${port}`);
});
