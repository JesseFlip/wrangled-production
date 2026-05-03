FROM python:3.11-slim

WORKDIR /app

# Copy all local packages/apps for dependency resolution
COPY packages/ /app/packages/
COPY apps/ /app/apps/

# Install dependencies in order
# 1. Core contracts
RUN pip install --no-cache-dir ./packages/contracts

# 2. Wrangler (contains the schedule data the API needs)
RUN pip install --no-cache-dir ./apps/wrangler

# 3. The API Hub itself
RUN pip install --no-cache-dir ./apps/api

# App Runner/ECS usually expects port 8080 or 80
EXPOSE 8080

# Run the FastAPI server
CMD ["uvicorn", "api.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
