from app import app

# Make the app available at module level for gunicorn
application = app

if __name__ == "__main__":
    app.run()