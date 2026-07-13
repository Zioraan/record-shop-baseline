FROM python:3.12-slim
WORKDIR /app
COPY frontends/dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY frontends/dashboard/dashboard.py .
EXPOSE 8501
CMD ["streamlit", "run", "dashboard.py", "--server.address=0.0.0.0", "--server.headless=true"]
