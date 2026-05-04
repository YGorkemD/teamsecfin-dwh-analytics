# Enterprise React (Vite) Frontend Dockerfile
FROM node:18-alpine

# Set the working directory inside the container
WORKDIR /app

# Copy package configurations first to leverage Docker layer caching
COPY package.json ./

# Install all dependencies cleanly
RUN npm install

# Copy the rest of the frontend source code
COPY . .

# Expose Vite's default development port
EXPOSE 5173

# Start the Vite server, bound to all network interfaces for Docker access
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]