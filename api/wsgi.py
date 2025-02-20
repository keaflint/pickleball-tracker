from api.app import app
import sys
import traceback

# This is for Vercel serverless deployment
app.debug = False

@app.errorhandler(500)
def handle_500_error(e):
    error_traceback = traceback.format_exc()
    print(f"500 Error: {error_traceback}", file=sys.stderr)
    return {
        "error": "Internal Server Error",
        "details": str(e),
        "traceback": error_traceback
    }, 500

if __name__ == '__main__':
    app.run() 