<<<<<<< HEAD
# Retail Management System (DailyInsight)

## How to run

1. **Start MySQL** and create the database/schema:
   - Open `db.sql` and run it in your MySQL client (or import the file).
   - This script creates the `dailyinsight` database with tables: `users`, `products`, `sales`.

2. **Create a Python virtual environment** (recommended):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure database connection (optional)**
   - The app uses these environment variables if set:
     - `MYSQL_HOST` (default: `127.0.0.1`)
     - `MYSQL_PORT` (default: `3306`)
     - `MYSQL_USER` (default: `root`)
     - `MYSQL_PASSWORD` (default: `root`)
     - `MYSQL_DB` (default: `dailyinsight`)

5. **Run the server**:
   ```bash
   python app.py
   ```

6. Open the app in your browser (default Flask port):
   - Usually `http://127.0.0.1:5000`

## Workflow

- **Signup/Login**
  - Users create an account (`/signup`) and then log in (`/login`).
  - Passwords are stored as hashes using `werkzeug.security`.
  - Logged-in users are protected by a `login_required` decorator.

- **Dashboard** (`/dashboard`)
  - Shows daily totals (today’s revenue, products count), low-stock alerts, and time-bucket activity for charting.

- **Sales entry** (`/sales`)
  - User records a sale for a product.
  - The server validates stock availability, inserts the row into `sales`, and decrements `products.stock`.

- **Stock management** (`/stock`)
  - Create/update/delete products.
  - All product operations are scoped to the logged-in user.

- **Reports** (`/reports`)
  - Generates a daily report for a selected date via query string (`?date=YYYY-MM-DD`).
  - Includes revenue summaries, payment split (Cash vs UPI), top product, and low/out-of-stock insights.

- **Monthly reports** (`/monthly-reports` + download)
  - Generates month-level aggregates and a paginated daily breakdown.
  - Download endpoint generates a PDF using `reportlab`:
    - `/monthly-reports-download?month=YYYY-MM`

- **Alerts API** (`/api/alerts/low-stock` and `/api/today/units-sold`)
  - Returns JSON responses used by the frontend for dashboard/notification widgets.

## Languages / technologies used

- **Python**: Flask web app (`app.py`) + server-side logic
- **HTML/Jinja2**: templates in `templates/`
- **CSS/JavaScript**: frontend assets in `static/`
- **MySQL**: database (schema in `db.sql`)
- **Additional Python libs** (from `requirements.txt`):
  - `Flask`
  - `mysql-connector-python`
  - `python-dotenv`
  - *(PDF generation uses `reportlab` inside `app.py` during download; it is imported at runtime.)*

## EC2 Deployment Steps

### 1. Connect to EC2

```
ssh -i key.pem ec2-user@<EC2-Public-IP>
```

### 2. Clone Repository

```
git clone <repository-url>
cd Retail-System
```

### 3. Create Virtual Environment

```
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

```
pip install -r requirements.txt
```

### 5. Start Gunicorn

```
nohup gunicorn --bind 127.0.0.1:5000 app:app > gunicorn.log 2>&1 &
```

### 6. Configure Nginx

Edit:

```
sudo nano /etc/nginx/nginx.conf
```

Add the following inside the `server` block:

```
location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Save and restart Nginx:

sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 7. Access Application

http://<EC2-Public-IP>



