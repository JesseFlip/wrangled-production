# Use a lightweight Python image
FROM python:3.11-slim

# Set working directory to project root
WORKDIR /app

# Copy the local packages and requirements
COPY packages/contracts ./packages/contracts
COPY apps/api ./apps/api

# Install dependencies
# We use -e for local paths to ensure they link correctly
RUN pip install --no-cache-dir ./packages/contracts
RUN pip install --no-cache-dir ./apps/api

# Expose the port App Runner will use
EXPOSE 8080

# Start the FastAPI hub
# We bind to 0.0.0.0 so AWS can reach the container
CMD ["uvicorn", "api.server.app:app", "--host", "0.0.0.0", "--port", "8080"]
