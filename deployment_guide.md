# Deployment Guide

## Quick Deploy with Render (Free Tier)

Render offers a free tier that works well for FastAPI applications:

1. Sign up at [Render](https://render.com) with your GitHub account
2. Connect your GitHub repository to Render
3. Click "New Web Service"
4. Select your repository
5. Render will automatically detect your Python app using the `render.yaml` file
6. Configure your environment variables in the Render dashboard:
   - Add your `OPENAI_API_KEY`
   - Set other environment variables as needed
7. Click "Create Web Service"
8. Your API will be deployed within minutes at a URL like `https://job-finder-api.onrender.com`

## Alternative: Deploy with Ngrok (Free for Local Tunneling)

If you want to expose your local development environment:

1. Install ngrok: 
   ```
   pip install pyngrok
   ```

2. Run your FastAPI app locally:
   ```
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

3. In another terminal, expose your app with ngrok:
   ```
   ngrok http 8000
   ```

4. Ngrok will provide a public URL like `https://a1b2c3d4.ngrok.io` that forwards to your local application

## Alternative: Digital Ocean App Platform (Free Tier)

Digital Ocean also offers a starter tier that's free:

1. Sign up at [Digital Ocean](https://www.digitalocean.com/products/app-platform/)
2. Create a new app and connect your GitHub repository
3. Select your repository
4. Configure as a Web Service
5. Set build command: `pip install -r requirements.txt`
6. Set run command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
7. Add environment variables (especially `OPENAI_API_KEY`)
8. Deploy your app

## Alternative: Heroku (Free Tier)

Though limited, Heroku's free tier can work for demo purposes:

1. Create a `runtime.txt` file with content: `python-3.9.16`
2. Create a `Procfile` file with content: `web: uvicorn main:app --host=0.0.0.0 --port=$PORT`
3. Sign up at [Heroku](https://heroku.com)
4. Install the Heroku CLI
5. Run the following commands:
   ```
   heroku login
   heroku create job-finder-api
   git push heroku main
   heroku config:set OPENAI_API_KEY=your_api_key_here
   ```
6. Set other environment variables with `heroku config:set`
