import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
import csv

# --- Paths & Configs ---
base_folder = "C:\\Users\\Dillo\\OneDrive\\ABC Kiosk Loyalty Program"
json_path = os.path.join(base_folder, "auto-beauty-rewards-565b20a521e3.json")
logo_path = os.path.join(base_folder, "clean_logo.png")
voucher_folder = os.path.join(base_folder, "vouchers")
csv_file = os.path.join(base_folder, "voucher_submissions.csv")
location = "Auto Beauty Centers of KC"
sender_email = "customerservice@autobeautycenters.com"
sender_password = "ABCkc3020?"
os.makedirs(voucher_folder, exist_ok=True)

# --- Google Sheets Setup ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
client = gspread.authorize(creds)
sheet = client.open("Auto Beauty Rewards Ledger").sheet1

# --- Name Lookup ---
def get_customer_name(email):
    try:
        summary_sheet = client.open("Auto Beauty Rewards Ledger").worksheet("Customer Loyalty Summary")
        records = summary_sheet.get_all_records()
        for row in records:
            if row['Email'].strip().lower() == email.strip().lower():
                return row['Name']
    except:
        pass
    return "Unknown"

# --- PDF Generator ---
def generate_voucher_pdf(name, reward):
    filename = os.path.join(voucher_folder, f"{name.replace(' ', '_')}_{reward.replace(' ', '_')}.pdf")
    c = canvas.Canvas(filename, pagesize=letter)
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(colors.HexColor("#003366"))
    c.drawCentredString(300, 750, "Auto Beauty Centers Voucher")
    c.setStrokeColor(colors.grey)
    c.setLineWidth(1)
    c.line(50, 735, 550, 735)
    c.setFillColor(colors.HexColor("#cc0000"))
    c.rect(50, 675, 500, 40, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(300, 687, reward)
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 14)
    c.drawString(60, 630, f"Customer Name: {name}")
    c.drawString(60, 605, f"Issue Date: {datetime.today().strftime('%Y-%m-%d')}")
    c.drawString(60, 580, "Please present this voucher at your next visit.")
    c.drawString(60, 555, "Limit one per customer. No cash value.")
    c.line(60, 510, 300, 510)
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(60, 495, "Authorized Signature")
    c.setFont("Helvetica", 10)
    c.drawString(60, 460, "Auto Beauty Centers • (816) 252-8700 • autobeautycenters.com")
    c.save()
    return filename

# --- Email Sender ---
def send_email(recipient, name, reward, pdf_path):
    msg = EmailMessage()
    msg["Subject"] = f"Your Voucher: {reward}"
    msg["From"] = sender_email
    msg["To"] = recipient
    msg.set_content(f"Hi {name},\n\nYour reward from Auto Beauty Centers is attached!\n\nWe look forward to seeing you soon.")

    with open(pdf_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=os.path.basename(pdf_path))

    alert_msg = EmailMessage()
    alert_msg["Subject"] = f"New Voucher: {name} | {reward}"
    alert_msg["From"] = sender_email
    alert_msg["To"] = sender_email
    alert_msg.set_content(f"{name} just submitted for '{reward}' at {location}.")

    with smtplib.SMTP("mail.autobeautycenters.com", 587) as smtp:
        smtp.starttls()
        smtp.login(sender_email, sender_password)
        smtp.send_message(msg)
        smtp.send_message(alert_msg)

# --- CSV Header Setup ---
if not os.path.exists(csv_file):
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["Date", "Name", "Email", "Reward", "Redeemed", "Points"])

# --- Ledger Logging ---
def log_submission(name, email, reward, points, redeemed="No"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_email = email.strip().lower()
    clean_name = name.strip()

    try:
        with open(csv_file, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([now, clean_name, clean_email, reward, redeemed, points])
        print("✅ CSV log successful")
    except Exception as e:
        print("❌ CSV log failed:", e)

    try:
        sheet.append_row([now, clean_name, clean_email, reward, redeemed, str(points)])
        print("✅ Google Sheet log successful")
    except Exception as e:
        print("❌ Google Sheet log failed:", e)

# --- Summary Logging ---
def log_summary(name, email, points_earned=0, points_redeemed=0, rewards_earned=0, rewards_redeemed=0):
    try:
        summary_sheet = client.open("Auto Beauty Rewards Ledger").worksheet("Customer Loyalty Summary")
        records = summary_sheet.get_all_records()
        row_index = None

        for i, row in enumerate(records, start=2):
            if row['Email'].strip().lower() == email.strip().lower():
                row_index = i
                break

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if row_index:
            current_row = records[row_index - 2]
            new_points_earned = int(current_row["Points Earned"]) + points_earned
            new_points_redeemed = int(current_row["Points Redeemed"]) + points_redeemed
            new_rewards_earned = int(current_row["Rewards Earned"]) + rewards_earned
            new_rewards_redeemed = int(current_row["Rewards Redeemed"]) + rewards_redeemed
            new_total = new_points_earned - new_points_redeemed

            summary_sheet.update(f"C{row_index}", [[
                new_points_earned,
                new_points_redeemed,
                new_rewards_earned,
                new_rewards_redeemed,
                new_total,
                now
            ]])
        else:
            total = points_earned - points_redeemed
            summary_sheet.append_row([
                name, email, points_earned, points_redeemed,
                rewards_earned, rewards_redeemed, total, now
            ])

    except Exception as e:
        print(f"❌ Summary sheet log failed: {e}")
# --- Streamlit Setup ---
st.set_page_config(page_title="Auto Beauty Voucher", layout="wide")
st.markdown(
    "<style>input, select, textarea, .stButton button {font-size: 1.3em; padding: 12px 20px;} .stTextInput > label, .stSelectbox > label {font-size: 1.2em; color: #003366;}</style>",
    unsafe_allow_html=True
)
st.markdown("<h1 style='text-align:center; color:#003366;'>Welcome to Auto Beauty Center</h1>", unsafe_allow_html=True)

# --- Customer Points Lookup ---
st.markdown("### 🔍 Check Your Points")
lookup_email = st.text_input("Enter your email to see your reward history", key="lookup_email")

if lookup_email and os.path.exists(csv_file):
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        headers = reader[0]
        rows = reader[1:]
        matched_rows = [row for row in rows if row[2].strip().lower() == lookup_email.strip().lower()]
        total_points = sum(int(row[5]) for row in matched_rows if row[5].isdigit())

        if matched_rows:
            st.success(f"Total Points: {total_points}")
            st.markdown("#### Your Past Rewards:")
            for row in matched_rows:
                st.markdown(f"- 🏆 {row[3]} on {row[0]} — Redeemed: **{row[4]}**, Points: {row[5]}")
        else:
            st.info("No records found for that email.")

st.markdown("---")

# --- Reward Claim Form ---
st.markdown("<h3 style='text-align:center; color:#8c8c8c;'>Claim Your Reward Below</h3>", unsafe_allow_html=True)
with st.form("voucher_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        customer_name = st.text_input("Customer Name", key="claim_name")
    with col2:
        customer_email = st.text_input("Customer Email", key="claim_email")

    reward_options = [
        "Free Interior Detail",
        "$50 Tow Credit",
        "Free Oil Change",
        "Free 4 Wheel Alignment",
        "$125 Credit for Paintless Dent Repair (PDR)",
        "Free Headlight Restoration",
        "Free Express Detail"
    ]
    reward_title = st.selectbox("Choose a Reward", reward_options, key="claim_reward")
    submitted = st.form_submit_button("🎁 Send Voucher")

if submitted and customer_name and customer_email and reward_title:
    pdf_path = generate_voucher_pdf(customer_name, reward_title)
    send_email(customer_email, customer_name, reward_title, pdf_path)
    log_submission(customer_name, customer_email, reward_title, 0)
    log_summary(
        name=customer_name,
        email=customer_email,
        rewards_earned=1
    )
    st.success("🎉 Voucher sent successfully!")

# --- Admin Login ---
st.markdown("---")
st.markdown("### 🔑 Admin Login")
admin_pw = st.text_input("Enter Admin Password", type="password", key="admin_pw_input")
if admin_pw == "ABCadmin2024":
    st.session_state["admin_verified"] = True
    st.success("🔓 Admin access granted.")
elif admin_pw:
    st.error("🚫 Incorrect password.")

# --- Admin Tools Panel ---
if st.session_state.get("admin_verified", False):
    st.subheader("🧰 Admin Dashboard")

    # 1️⃣ Register New Customer
    with st.form("register_customer"):
        st.write("👤 Register New Loyalty Customer")
        reg_name = st.text_input("Full Name", key="reg_name")
        reg_email = st.text_input("Email", key="reg_email")
        submit_register = st.form_submit_button("Register Customer")

        if submit_register and reg_name and reg_email:
            log_summary(name=reg_name, email=reg_email)
            st.success(f"✅ {reg_name} registered in the loyalty program.")

    st.markdown("---")

    # 2️⃣ Add Points Only (No Reward)
    with st.form("add_points"):
        st.write("➕ Add Points to Existing Customer")
        points_email = st.text_input("Customer Email", key="points_email")
        added_points = st.number_input("Points to Add", min_value=1, step=1, key="points_amount")
        submit_points = st.form_submit_button("Add Points")

        if submit_points and points_email and added_points:
            name = get_customer_name(points_email)
            log_submission(name, points_email, "Points Only", int(added_points))
            log_summary(name=name, email=points_email, points_earned=int(added_points))
            st.success(f"✅ {added_points} points added to {points_email}'s account.")
    # 3️⃣ Issue Voucher Only (No Points)
    with st.form("issue_voucher_only"):
        st.write("🎁 Issue Reward Without Points")
        voucher_name = st.text_input("Customer Name", key="voucher_name")
        voucher_email = st.text_input("Customer Email", key="voucher_email")
        voucher_title = st.text_input("Reward Title", key="voucher_title")
        submit_voucher = st.form_submit_button("Send Voucher")

        if submit_voucher and voucher_name and voucher_email and voucher_title:
            pdf_path = generate_voucher_pdf(voucher_name, voucher_title)
            send_email(voucher_email, voucher_name, voucher_title, pdf_path)
            log_submission(voucher_name, voucher_email, voucher_title, 0)
            log_summary(
                name=voucher_name,
                email=voucher_email,
                rewards_earned=1
            )
            st.success(f"✅ Voucher for '{voucher_title}' sent to {voucher_name}.")

    st.markdown("---")

    # 4️⃣ Redeem Points Only
    with st.form("redeem_points_only"):
        st.write("🔻 Redeem Points Only (No Voucher)")
        redeem_email = st.text_input("Customer Email to Redeem Points", key="redeem_email")
        redeem_amount = st.number_input("Points to Redeem", min_value=1, step=1, key="redeem_amount")
        submit_redeem_points = st.form_submit_button("Redeem Points")

        if submit_redeem_points and redeem_email and redeem_amount:
            name = get_customer_name(redeem_email)
            log_submission(name, redeem_email, "Points Redeemed", -int(redeem_amount))
            log_summary(
                name=name,
                email=redeem_email,
                points_redeemed=int(redeem_amount)
            )
            st.success(f"✅ {redeem_amount} points redeemed for {redeem_email}.")

    st.markdown("---")

    # 5️⃣ Mark Voucher as Redeemed
    with st.form("mark_voucher_redeemed"):
        st.write("🎟️ Mark a Voucher as Redeemed")
        redeemed_email = st.text_input("Customer Email for Voucher Redemption", key="redeemed_email")
        redeemed_title = st.text_input("Reward Title (optional)", key="redeemed_title")
        submit_redeemed_voucher = st.form_submit_button("Log Voucher Redemption")

        if submit_redeemed_voucher and redeemed_email:
            name = get_customer_name(redeemed_email)
            reward_title = redeemed_title or "Reward Redeemed"
            log_submission(name, redeemed_email, reward_title, 0, redeemed="Yes")
            log_summary(
                name=name,
                email=redeemed_email,
                rewards_redeemed=1
            )
            st.success(f"✅ Reward marked redeemed for {redeemed_email}.")

# --- Footer Branding ---
st.markdown("---")
st.image(logo_path, width=350)
st.markdown(
    "<div style='text-align:center; color:gray; font-size:0.9em;'>"
    "Auto Beauty Centers • (816) 252-8700 • "
    "<a href='https://autobeautycenters.com' target='_blank'>autobeautycenters.com</a>"
    "</div>",
    unsafe_allow_html=True
)