from api.app import app
import sys
import traceback

@app.errorhandler(500)
def handle_500_error(e):
    # Log the full error traceback
    error_traceback = traceback.format_exc()
    print(f"500 Error: {error_traceback}", file=sys.stderr)
    return {
        "error": "Internal Server Error",
        "details": str(e),
        "traceback": error_traceback
    }, 500

# This is for Vercel serverless deployment
if __name__ == '__main__':
    app.run() 