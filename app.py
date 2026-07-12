import os
import re
import boto3
from io import BytesIO
from datetime import date, datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # MySQL connection (root/root, 127.0.0.1)
    app.config.update(
        DB_HOST=os.getenv("MYSQL_HOST", "database-1.c8jq4gc42gdl.us-east-1.rds.amazonaws.com"),
        DB_PORT=int(os.getenv("MYSQL_PORT", "3306")),
        DB_USER=os.getenv("MYSQL_USER", "admin"),
        DB_PASSWORD=os.getenv("MYSQL_PASSWORD", "vijaya21"),
        DB_NAME=os.getenv("MYSQL_DB", "dailyinsight"),
        )
        
    def get_db():
        return mysql.connector.connect(
            host=app.config["DB_HOST"],
            port=app.config["DB_PORT"],
            user=app.config["DB_USER"],
            password=app.config["DB_PASSWORD"],
            database=app.config["DB_NAME"],
        )

    def login_required(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            return f(*args, **kwargs)

        return wrapper

    def email_is_valid(email: str) -> bool:
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""))

    @app.get("/")
    def home():
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return redirect(url_for("signup"))

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            shop_name = (request.form.get("shop_name") or "").strip()
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""

            if not name or not shop_name or not email or not password:
                flash("All fields are required.", "error")
                return redirect(url_for("signup"))
            if not email_is_valid(email):
                flash("Invalid email format.", "error")
                return redirect(url_for("signup"))
            if len(password) < 4:
                flash("Password must be at least 4 characters.", "error")
                return redirect(url_for("signup"))

            password_hash = generate_password_hash(password)

            try:
                with get_db() as conn:
                    cur = conn.cursor(dictionary=True)
                    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
                    if cur.fetchone():
                        flash("Email already registered. Please login.", "error")
                        return redirect(url_for("login"))

                    cur.execute(
                        "INSERT INTO users (name, shop_name, email, password_hash) VALUES (%s,%s,%s,%s)",
                        (name, shop_name, email, password_hash),
                    )
                    conn.commit()
                    flash("Signup successful. Please login.", "success")
                    return redirect(url_for("login"))
            except Error as e:
                # Show actual MySQL error in server output
                print("[signup db error]", e)
                # Extra debug: print config (do not print password)
                print("[db config]", {"host": app.config['DB_HOST'], "user": app.config['DB_USER'], "db": app.config['DB_NAME']})

                flash("Database error during signup.", "error")
                return redirect(url_for("signup"))

        return render_template("signup.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""

            if not email or not password:
                flash("Email and password are required.", "error")
                return redirect(url_for("login"))

            try:
                with get_db() as conn:
                    cur = conn.cursor(dictionary=True)
                    cur.execute("SELECT id, name, password_hash FROM users WHERE email=%s", (email,))
                    row = cur.fetchone()
                    if not row or not check_password_hash(row["password_hash"], password):
                        flash("Invalid credentials.", "error")
                        return redirect(url_for("login"))

                    session["user_id"] = row["id"]
                    session["user_name"] = row.get("name")
                    return redirect(url_for("dashboard"))
            except Error as e:
                print("[login db error]", e)
                flash("Database error during login.", "error")
                return redirect(url_for("login"))

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Logged out successfully.", "success")
        return redirect(url_for("login"))

    def current_user_id():
        return session["user_id"]

    def fetch_products(user_id):
        with get_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT id, name, sku, price, stock FROM products WHERE user_id=%s ORDER BY name ASC",
                (user_id,),
            )
            return cur.fetchall()


    @app.route("/dashboard")
    @login_required
    def dashboard():
        user_id = current_user_id()

        today = date.today()
        today_start = datetime(today.year, today.month, today.day)
        today_end = today_start + timedelta(days=1)

        # Time buckets for "Today’s Sales Activity" chart (aligned to required X-axis).
        bucket_hours = [9, 11, 13, 15, 17, 19, 21]
        bucket_labels = []
        for h in bucket_hours:
            suffix = 'AM' if h < 12 else 'PM'
            hr12 = h % 12
            if hr12 == 0:
                hr12 = 12
            bucket_labels.append(f"{hr12} {suffix}")


        with get_db() as conn:
            cur = conn.cursor(dictionary=True)

            # Today’s Total Sales
            cur.execute(
                "SELECT COALESCE(SUM(total_price),0) AS total_sales FROM sales WHERE user_id=%s AND sold_at >= %s AND sold_at < %s",
                (user_id, today_start, today_end),
            )
            total_sales = float(cur.fetchone()["total_sales"] or 0)

            # Total Products Sold today (units)
            cur.execute(
                """
                SELECT COALESCE(SUM(s.quantity),0) AS cnt
                FROM sales s
                WHERE s.user_id=%s AND s.sold_at >= %s AND s.sold_at < %s
                """,
                (user_id, today_start, today_end),
            )
            total_products_sold = int(cur.fetchone()["cnt"] or 0)

            # Busy Hours Trend: compute activity (units sold) per time slot only.
            now_dt = datetime.now()

            bucket_activity = []
            for h in bucket_hours:
                start_dt = datetime(today.year, today.month, today.day, h, 0, 0)
                end_dt = start_dt + timedelta(hours=2)
                if start_dt < today_start:
                    start_dt = today_start
                if end_dt > today_end:
                    end_dt = today_end

                # Hide future buckets.
                if now_dt < start_dt:
                    bucket_activity.append(None)
                    continue

                cur.execute(
                    """
                    SELECT COALESCE(SUM(s.quantity),0) AS units_sold
                    FROM sales s
                    WHERE s.user_id=%s AND s.sold_at >= %s AND s.sold_at < %s
                    """,
                    (user_id, start_dt, end_dt),
                )
                row = cur.fetchone()
                units_sold = int(row["units_sold"] or 0)
                bucket_activity.append(units_sold)

            # Backward-compat: keep template variable name today_sales_by_time, but now it holds activity units.
            bucket_values = bucket_activity


            # activity_score_current was previously derived from units-sold buckets.
            # It is not used by the dashboard template currently, so keep it safe.
            # (If you later display it, we can compute from revenue/units as desired.)
            activity_score_current = 0






            # Total Products
            cur.execute("SELECT COUNT(*) AS cnt FROM products WHERE user_id=%s", (user_id,))
            total_products = cur.fetchone()["cnt"]


            # IMPORTANT: total_products_sold was already computed above (do not overwrite).

            # Low stock alerts (stock <= 5)

            cur.execute(
                "SELECT id, name, stock FROM products WHERE user_id=%s AND stock <= 5 ORDER BY stock ASC",
                (user_id,),
            )
            low_stock = cur.fetchall()

            # Active customers today
            # Schema note: `sales` table in this project does not include a customer_id.
            # Fallback: use count of distinct products sold today as a proxy for "activity".
            cur.execute(
                """
                SELECT COUNT(DISTINCT s.product_id) AS cnt
                FROM sales s
                WHERE s.user_id=%s AND s.sold_at >= %s AND s.sold_at < %s
                """,
                (user_id, today_start, today_end),
            )
            active_customers = cur.fetchone()["cnt"]


        return render_template(
            "dashboard.html",
            user_name=session.get("user_name") or "-",
            total_sales=float(total_sales),
            total_products=int(total_products),
            low_stock=low_stock,
            active_customers=int(active_customers or 0),
            labels=bucket_labels,
            today_sales_by_time=bucket_values,
            activity_score_current=activity_score_current,
        )

    @app.get("/api/today/units-sold")
    @login_required
    def api_today_units_sold():
        user_id = current_user_id()
        today = date.today()
        today_start = datetime(today.year, today.month, today.day)
        today_end = today_start + timedelta(days=1)

        with get_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT COALESCE(SUM(s.quantity),0) AS cnt
                FROM sales s
                WHERE s.user_id=%s AND s.sold_at >= %s AND s.sold_at < %s
                """,
                (user_id, today_start, today_end),
            )
            cnt = int((cur.fetchone() or {}).get("cnt") or 0)

        return jsonify({"total_units_sold": cnt})




    @app.route("/sales", methods=["GET", "POST"])
    @login_required
    def sales_entry():
        user_id = current_user_id()

        if request.method == "POST":
            product_id = int(request.form.get("product_id"))
            payment_type = (request.form.get("payment_type") or "").strip()
            quantity = int(request.form.get("quantity"))
            

            if payment_type not in ("Cash", "UPI"):
                flash("Payment type is required.", "error")
                return redirect(url_for("sales_entry"))

            if quantity <= 0:
                flash("Quantity must be greater than 0.", "error")
                return redirect(url_for("sales_entry"))

            try:
                with get_db() as conn:
                    cur = conn.cursor(dictionary=True)

                    cur.execute(
                        "SELECT stock, price FROM products WHERE id=%s AND user_id=%s FOR UPDATE",
                        (product_id, user_id),
                    )
                    prod = cur.fetchone()
                    if not prod:
                        flash("Invalid product.", "error")
                        return redirect(url_for("sales_entry"))
                    if prod["stock"] < quantity:
                        flash("Not enough stock for this sale.", "error")
                        return redirect(url_for("sales_entry"))
                    unit_price = float(prod["price"])
                    total_price = unit_price * quantity

                    cur.execute(
                        "INSERT INTO sales (user_id, product_id, quantity, payment_type, unit_price, total_price) VALUES (%s,%s,%s,%s,%s,%s)",
                        (user_id, product_id, quantity, payment_type, unit_price, total_price),
                    )

                    cur.execute(
                        "UPDATE products SET stock = stock - %s WHERE id=%s AND user_id=%s",
                        (quantity, product_id, user_id),
                    )
                    
                    # SNS START
                    cur.execute(
                       "SELECT name, stock FROM products WHERE id=%s AND user_id=%s",
                       (product_id, user_id),
                    )
                    product = cur.fetchone()

                    sns = boto3.client("sns", region_name="us-east-1")

                    if product and product["stock"] <= 5:
                       sns.publish(
                       TopicArn="arn:aws:sns:us-east-1:116904976040:mytopic",
                       Subject="Low Stock Alert",
                       Message=f"{product['name']} stock is low. Remaining stock: {product['stock']}"
                       )
                    # SNS END
                    
                    conn.commit()
                    flash("Sale recorded successfully.", "success")
                    return redirect(url_for("dashboard"))
            except Error as e:
                print("[sale db error]", e)
                flash("Database error while recording sale.", "error")
                return redirect(url_for("sales_entry"))

        products = fetch_products(user_id)
        return render_template("sales.html", products=products)


    @app.route("/stock", methods=["GET", "POST"])
    @login_required
    def stock_management():
        user_id = current_user_id()

        if request.method == "POST":
            action = request.form.get("action")
            product_id = request.form.get("product_id")
            name = (request.form.get("name") or "").strip()
            price = request.form.get("price")
            stock = request.form.get("stock")


            try:
                price = float(price)
                stock = int(stock)
            except Exception:
                flash("Invalid price/stock values.", "error")
                return redirect(url_for("stock_management"))

            if not name:
                flash("Product name is required.", "error")
                return redirect(url_for("stock_management"))

            try:
                with get_db() as conn:
                    cur = conn.cursor()
                    if action == "create":
                        cur.execute(
                            "INSERT INTO products (user_id, name, price, stock) VALUES (%s,%s,%s,%s)",
                            (user_id, name, price, stock),
                        )
                    elif action == "update":
                        if not product_id:
                            flash("Missing product id.", "error")
                            return redirect(url_for("stock_management"))
                        cur.execute(
                            "UPDATE products SET name=%s, price=%s, stock=%s WHERE id=%s AND user_id=%s",
                            (name, price, stock, int(product_id), user_id),
                        )

                    elif action == "delete":
                        if not product_id:
                            flash("Missing product id.", "error")
                            return redirect(url_for("stock_management"))
                        cur.execute("DELETE FROM products WHERE id=%s AND user_id=%s", (int(product_id), user_id))

                    conn.commit()
                    flash("Stock updated successfully.", "success")
                    return redirect(url_for("stock_management"))
            except Error as e:
                print("[stock db error]", e)
                flash("Database error while managing stock.", "error")
                return redirect(url_for("stock_management"))

        with get_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT id, name, price, stock FROM products WHERE user_id=%s ORDER BY name ASC",
                (user_id,),
            )
            products = cur.fetchall()

        return render_template("stock.html", products=products)


    @app.route("/reports", methods=["GET"])
    @login_required
    def reports():
        user_id = current_user_id()
        
        date_str = (request.args.get("date") or "").strip()

        # Only show report content after explicit user generation (date passed in query string).
        show_report = bool(date_str)

        today = date.today()
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else today
        except ValueError:
            selected_date = today

        prev_date = selected_date - timedelta(days=1)

        day_start = datetime(selected_date.year, selected_date.month, selected_date.day)
        day_end = day_start + timedelta(days=1)

        prev_start = datetime(prev_date.year, prev_date.month, prev_date.day)
        prev_end = prev_start + timedelta(days=1)

        with get_db() as conn:
            cur = conn.cursor(dictionary=True)

            # Summary: total revenue for selected day
            cur.execute(
                """
                SELECT COALESCE(SUM(total_price),0) AS total_revenue
                FROM sales
                WHERE user_id=%s AND sold_at >= %s AND sold_at < %s
                """,
                (user_id, day_start, day_end),
            )
            report_total_revenue = float((cur.fetchone() or {}).get("total_revenue") or 0)

            # Summary: total transactions + products sold
            cur.execute(
                """
                SELECT
                  COUNT(*) AS tx_count,
                  COALESCE(SUM(quantity),0) AS total_qty
                FROM sales
                WHERE user_id=%s AND sold_at >= %s AND sold_at < %s
                """,
                (user_id, day_start, day_end),
            )
            row = cur.fetchone() or {}
            report_total_transactions = int(row.get("tx_count") or 0)
            report_total_products_sold = int(row.get("total_qty") or 0)

            # Payment split (Cash vs UPI) for selected day
            cur.execute(
                """
                SELECT
                  COALESCE(SUM(CASE WHEN payment_type='Cash' THEN total_price ELSE 0 END),0) AS cash_revenue,
                  COALESCE(SUM(CASE WHEN payment_type='UPI' THEN total_price ELSE 0 END),0) AS upi_revenue
                FROM sales
                WHERE user_id=%s AND sold_at >= %s AND sold_at < %s
                """,
                (user_id, day_start, day_end),
            )
            split_row = cur.fetchone() or {}
            report_cash_revenue = float(split_row.get("cash_revenue") or 0)
            report_upi_revenue = float(split_row.get("upi_revenue") or 0)

            report_payment_total = report_cash_revenue + report_upi_revenue
            if report_payment_total > 0:
                report_cash_pct = (report_cash_revenue / report_payment_total) * 100.0
                report_upi_pct = (report_upi_revenue / report_payment_total) * 100.0
            else:
                report_cash_pct = 0.0
                report_upi_pct = 0.0

            # Sales table rows for selected day
            cur.execute(
                """
                SELECT
                  p.name AS product_name,
                  SUM(s.quantity) AS qty,
                  SUM(s.total_price) AS revenue
                FROM sales s
                JOIN products p ON p.id = s.product_id
                WHERE s.user_id=%s AND s.sold_at >= %s AND s.sold_at < %s
                GROUP BY p.id, p.name
                ORDER BY qty DESC
                """,
                (user_id, day_start, day_end),
            )
            report_sales_rows = cur.fetchall()
            for r in report_sales_rows:
                r["qty"] = int(r.get("qty") or 0)
                r["revenue"] = float(r.get("revenue") or 0)

            # Top selling product for selected day
            cur.execute(
                """
                SELECT p.name AS product_name, SUM(s.quantity) AS qty
                FROM sales s
                JOIN products p ON p.id = s.product_id
                WHERE s.user_id=%s AND s.sold_at >= %s AND s.sold_at < %s
                GROUP BY p.id, p.name
                ORDER BY qty DESC
                LIMIT 1
                """,
                (user_id, day_start, day_end),
            )
            top_row = cur.fetchone()
            report_top_selling_product = top_row.get("product_name") if top_row else "-"

            # Best selling product (same as top selling product for day)
            report_best_selling_product = report_top_selling_product

            # Low stock / out of stock insights (current inventory)
            cur.execute(
                """
                SELECT id, name, stock
                FROM products
                WHERE user_id=%s AND stock > 0 AND stock <= 5
                ORDER BY stock ASC
                """,
                (user_id,),
            )
            report_low_stock = cur.fetchall()

            cur.execute(
                """
                SELECT id, name, stock
                FROM products
                WHERE user_id=%s AND stock <= 0
                ORDER BY name ASC
                """,
                (user_id,),
            )
            report_out_of_stock = cur.fetchall()

            # Previous day revenue for delta
            cur.execute(
                """
                SELECT COALESCE(SUM(total_price),0) AS total_revenue
                FROM sales
                WHERE user_id=%s AND sold_at >= %s AND sold_at < %s
                """,
                (user_id, prev_start, prev_end),
            )
            prev_row = cur.fetchone() or {}
            report_prev_day_revenue = float(prev_row.get("total_revenue") or 0)

        report_revenue_delta = report_total_revenue - report_prev_day_revenue

        return render_template(
            "reports.html",
            show_report=show_report,
            selected_date=selected_date.strftime("%Y-%m-%d"),
            prev_date=prev_date.strftime("%Y-%m-%d"),
            report_total_revenue=report_total_revenue,
            report_total_products_sold=report_total_products_sold,
            report_total_transactions=report_total_transactions,
            report_top_selling_product=report_top_selling_product,
            report_sales_rows=report_sales_rows,
            report_best_selling_product=report_best_selling_product,
            report_low_stock=report_low_stock,
            report_out_of_stock=report_out_of_stock,
            report_today_revenue=report_total_revenue,
            report_prev_day_revenue=report_prev_day_revenue,
            report_revenue_delta=report_revenue_delta,
            report_cash_revenue=report_cash_revenue,
            report_upi_revenue=report_upi_revenue,
            report_cash_pct=report_cash_pct,
            report_upi_pct=report_upi_pct,
        )

    @app.route("/monthly-reports", methods=["GET"])
    @login_required
    def monthly_reports():
        user_id = current_user_id()

        # month is expected as YYYY-MM (example: 2026-06)
        month_str = (request.args.get("month") or "").strip()
        page = int((request.args.get("page") or "1").strip() or "1")
        page = max(page, 1)
        per_page = 10  # pagination size over daily rows

        today = date.today()
        try:
            selected_month_date = datetime.strptime(month_str, "%Y-%m").date() if month_str else date(today.year, today.month, 1)
        except ValueError:
            selected_month_date = date(today.year, today.month, 1)

        selected_year = selected_month_date.year
        selected_month = selected_month_date.month

        # Start/end boundaries for selected month
        month_start = datetime(selected_year, selected_month, 1)
        if selected_month == 12:
            next_month_start = datetime(selected_year + 1, 1, 1)
        else:
            next_month_start = datetime(selected_year, selected_month + 1, 1)

        # Previous month boundaries
        if selected_month == 1:
            prev_month_start = datetime(selected_year - 1, 12, 1)
        else:
            prev_month_start = datetime(selected_year, selected_month - 1, 1)
        prev_month_end = month_start

        with get_db() as conn:
            cur = conn.cursor(dictionary=True)

            # Monthly Revenue
            cur.execute(
                """
                SELECT COALESCE(SUM(total_price),0) AS total_revenue
                FROM sales
                WHERE user_id=%s AND sold_at >= %s AND sold_at < %s
                """,
                (user_id, month_start, next_month_start),
            )
            monthly_revenue = float((cur.fetchone() or {}).get("total_revenue") or 0)

            # Previous Month Revenue
            cur.execute(
                """
                SELECT COALESCE(SUM(total_price),0) AS total_revenue
                FROM sales
                WHERE user_id=%s AND sold_at >= %s AND sold_at < %s
                """,
                (user_id, prev_month_start, prev_month_end),
            )
            prev_month_revenue = float((cur.fetchone() or {}).get("total_revenue") or 0)

            # Total Orders This Month (orders = sales rows count)
            cur.execute(
                """
                SELECT COUNT(*) AS order_count
                FROM sales
                WHERE user_id=%s AND sold_at >= %s AND sold_at < %s
                """,
                (user_id, month_start, next_month_start),
            )
            total_orders_this_month = int((cur.fetchone() or {}).get("order_count") or 0)

            # Daily breakdown (group by day)
            # Use DATE(sold_at) for day label; order by date.
            cur.execute(
                """
                SELECT
                  DATE(sold_at) AS sold_date,
                  COUNT(*) AS orders,
                  COALESCE(SUM(total_price),0) AS revenue
                FROM sales
                WHERE user_id=%s AND sold_at >= %s AND sold_at < %s
                GROUP BY DATE(sold_at)
                ORDER BY sold_date ASC
                """,
                (user_id, month_start, next_month_start),
            )
            all_daily_rows = cur.fetchall() or []

        # Pagination in Python (simple & robust)
        total_rows = len(all_daily_rows)
        total_pages = max((total_rows + per_page - 1) // per_page, 1)
        page = min(page, total_pages)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_rows = all_daily_rows[start_idx:end_idx]

        daily_rows = []
        month_display = selected_month_date.strftime("%B %Y")
        month_value = selected_month_date.strftime("%Y-%m")
        for r in page_rows:
            sold_date = r.get("sold_date")
            if isinstance(sold_date, (datetime, date)):
                day_label = sold_date.strftime("%d %b %Y")
            else:
                # fallback string parsing
                day_label = str(sold_date)
            daily_rows.append({
                "day_label": day_label,
                "orders": int(r.get("orders") or 0),
                "revenue": float(r.get("revenue") or 0),
            })

        pagination = {
            "page": page,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_page": page - 1,
            "next_page": page + 1,
        }

        return render_template(
            "monthly_reports.html",
            selected_month_value=month_value,
            month_display=month_display,
            monthly_revenue=monthly_revenue,
            prev_month_revenue=prev_month_revenue,
            total_orders_this_month=total_orders_this_month,
            daily_rows=daily_rows,
            pagination=pagination,
            # used by pagination links in template
            selected_month_value_for_links=month_value,
        )

    @app.get("/monthly-reports-download")
    @login_required
    def monthly_reports_download():
        # Generate and download a PDF report for the selected month.
        user_id = current_user_id()
        month_str = (request.args.get("month") or "").strip()
        if not month_str:
            flash("Please select a month before downloading the report.", "error")
            return redirect(url_for("monthly_reports"))

        today = date.today()
        try:
            selected_month_date = datetime.strptime(month_str, "%Y-%m").date()
        except ValueError:
            flash("Please select a valid month.", "error")
            return redirect(url_for("monthly_reports"))

        selected_year = selected_month_date.year
        selected_month = selected_month_date.month

        month_start = datetime(selected_year, selected_month, 1)
        if selected_month == 12:
            next_month_start = datetime(selected_year + 1, 1, 1)
        else:
            next_month_start = datetime(selected_year, selected_month + 1, 1)

        prev_month_start = datetime(selected_year, selected_month, 1)
        if selected_month == 1:
            prev_month_start = datetime(selected_year - 1, 12, 1)
            prev_month_end = month_start
        else:
            prev_month_start = datetime(selected_year, selected_month - 1, 1)
            prev_month_end = month_start

        # Fetch monthly + previous monthly summaries and daily breakdown
        with get_db() as conn:
            cur = conn.cursor(dictionary=True)

            cur.execute(
                """
                SELECT COALESCE(SUM(total_price),0) AS total_revenue
                FROM sales
                WHERE user_id=%s AND sold_at >= %s AND sold_at < %s
                """,
                (user_id, month_start, next_month_start),
            )
            monthly_revenue = float((cur.fetchone() or {}).get("total_revenue") or 0)

            cur.execute(
                """
                SELECT COALESCE(SUM(total_price),0) AS total_revenue
                FROM sales
                WHERE user_id=%s AND sold_at >= %s AND sold_at < %s
                """,
                (user_id, prev_month_start, prev_month_end),
            )
            prev_month_revenue = float((cur.fetchone() or {}).get("total_revenue") or 0)

            cur.execute(
                """
                SELECT COUNT(*) AS order_count
                FROM sales
                WHERE user_id=%s AND sold_at >= %s AND sold_at < %s
                """,
                (user_id, month_start, next_month_start),
            )
            total_orders_this_month = int((cur.fetchone() or {}).get("order_count") or 0)

            cur.execute(
                """
                SELECT
                  DATE(sold_at) AS sold_date,
                  COUNT(*) AS orders,
                  COALESCE(SUM(total_price),0) AS revenue
                FROM sales
                WHERE user_id=%s AND sold_at >= %s AND sold_at < %s
                GROUP BY DATE(sold_at)
                ORDER BY sold_date ASC
                """,
                (user_id, month_start, next_month_start),
            )
            rows = cur.fetchall() or []

        # PDF generation with reportlab
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.pdfgen import canvas
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        month_display = selected_month_date.strftime("%B %Y")
        filename = (
            f"User_{user_id}_Monthly_Report_"
            f"{selected_month_date.strftime('%B_%Y')}.pdf"
        )

        print("CURRENT USER ID:", user_id)
        print("FILENAME:", filename)

        buffer = BytesIO()
        styles = getSampleStyleSheet()
        style_title = styles["Heading1"]
        style_title.fontName = "Helvetica-Bold"
        style_title.fontSize = 16

        style_sub = styles["Normal"]
        style_sub.fontName = "Helvetica"
        style_sub.fontSize = 10

        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)

        elements = []
        elements.append(Paragraph("DailyInsight", styles["Heading2"]))
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Monthly Revenue Report", style_title))
        elements.append(Paragraph(f"Selected Month: {month_display}", style_sub))
        elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%d %b %Y, %I:%M %p')}", style_sub))
        elements.append(Spacer(1, 12))

        # Summary section
        elements.append(Paragraph("Summary", styles["Heading3"]))
        summary_data = [
            ["Monthly Revenue", f"₹ {monthly_revenue:,.2f}"],
            ["Previous Month Revenue", f"₹ {prev_month_revenue:,.2f}"],
            ["Total Orders This Month", f"{total_orders_this_month}"],
        ]
        summary_table = Table(summary_data, colWidths=[240, 240])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 14))

        elements.append(Paragraph("Daily Breakdown", styles["Heading3"]))

        table_data = [["Date", "Orders", "Revenue"]]
        for r in rows:
            sold_date = r.get("sold_date")
            if isinstance(sold_date, (datetime, date)):
                day_label = sold_date.strftime("%d %b %Y")
            else:
                day_label = str(sold_date)
            table_data.append([
                day_label,
                str(int(r.get("orders") or 0)),
                f"₹ {float(r.get('revenue') or 0):,.0f}",
            ])

        daily_table = Table(table_data, colWidths=[180, 80, 140])
        daily_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(daily_table)

        elements.append(Spacer(1, 10))
        elements.append(Paragraph("Generated by DailyInsight", styles["Normal"]))

        doc.build(elements)

        pdf_bytes = buffer.getvalue()
        
        
        
        try:
            s3 = boto3.client("s3")
            response = s3.put_object(
                Bucket="dailyinsight-reportss",
                Key=filename,
                Body=pdf_bytes,
                ContentType="application/pdf"
                )
            print("UPLOAD SUCCESS")
            print(response)
        except Exception as e:
            print("UPLOAD FAILED:", e)


        from flask import Response
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
        
        


    
    
    
    @app.get("/api/alerts/low-stock")

    @login_required
    def api_low_stock():
        user_id = current_user_id()
        with get_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT id, name, stock FROM products WHERE user_id=%s AND stock <= 5 ORDER BY stock ASC",
                (user_id,),
            )
            low_stock = cur.fetchall()
            return jsonify({"items": low_stock})

    return app





app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)