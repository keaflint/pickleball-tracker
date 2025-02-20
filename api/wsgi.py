from api.app import app

# This is for Vercel serverless deployment
app.debug = False

if __name__ == '__main__':
    app.run() 