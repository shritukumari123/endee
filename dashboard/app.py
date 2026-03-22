import streamlit as st
import pandas as pd
import joblib
import time

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="Customer Churn Prediction",
    layout="centered"
)

# ---------------- LOAD MODEL ----------------
model = joblib.load("xgboost_churn_model.pkl")
features = joblib.load("model_features.pkl")

# ---------------- TITLE ----------------
st.title("Customer Churn Prediction")
st.write("Predict customer churn risk using a trained XGBoost model.")

st.divider()

# ---------------- INPUT SECTION ----------------
st.subheader("Customer Information")

tenure = st.slider("Tenure (months)", 0, 72, 12)
monthly_charges = st.slider("Monthly Charges ($)", 20.0, 120.0, 70.0)

contract = st.selectbox(
    "Contract Type",
    ["Month-to-month", "One year", "Two year"]
)

internet = st.selectbox(
    "Internet Service",
    ["DSL", "Fiber optic", "No"]
)

payment = st.selectbox(
    "Payment Method",
    [
        "Electronic check",
        "Mailed check",
        "Bank transfer (automatic)",
        "Credit card (automatic)"
    ]
)

paperless = st.selectbox(
    "Paperless Billing",
    ["Yes", "No"]
)

st.divider()

# ---------------- BUILD FEATURE VECTOR ----------------
input_dict = dict.fromkeys(features, 0)

input_dict["tenure"] = tenure
input_dict["MonthlyCharges"] = monthly_charges

if contract != "Month-to-month":
    col = f"Contract_{contract}"
    if col in input_dict:
        input_dict[col] = 1

if internet != "No":
    col = f"InternetService_{internet}"
    if col in input_dict:
        input_dict[col] = 1

payment_col = f"PaymentMethod_{payment}"
if payment_col in input_dict:
    input_dict[payment_col] = 1

input_dict["PaperlessBilling_Yes"] = 1 if paperless == "Yes" else 0

input_df = pd.DataFrame([input_dict])

# ---------------- PREDICTION ----------------
if st.button("Predict Churn Risk"):
    with st.spinner("Processing..."):
        time.sleep(0.8)

    prob = model.predict_proba(input_df)[0][1]

    st.subheader("Prediction Result")

    if prob >= 0.35:
        st.error(f"High Churn Risk\n\nProbability: {prob:.2f}")
    else:
        st.success(f"Low Churn Risk\n\nProbability: {prob:.2f}")

st.divider()
st.caption("XGBoost Model | End-to-End ML Deployment")
