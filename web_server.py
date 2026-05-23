"""
╔══════════════════════════════════════════════════════════════╗
║     🔥 NETFLIX ULTIMATE BOT - WEB SERVER MODULE 🔥         ║
║     Handles Direct Login Links                              ║
╚══════════════════════════════════════════════════════════════╝
"""

import logging
from aiohttp import web
from config import WEB_HOST, WEB_PORT, BOT_VERSION

logger = logging.getLogger("NetflixWeb")


class WebServer:
    """Web server for handling Netflix direct login links"""

    def __init__(self, db):
        self.db = db
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        """Setup web routes"""
        self.app.router.add_get('/', self.index)
        self.app.router.add_get('/login/{token}', self.login_page)
        self.app.router.add_get('/api/cookie/{token}', self.get_cookie)
        self.app.router.add_get('/health', self.health_check)

    async def index(self, request):
        """Index page"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Netflix Premium Bot</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    background: #141414;
                    color: #fff;
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                }
                .container {
                    text-align: center;
                    padding: 40px;
                }
                h1 {
                    color: #E50914;
                    font-size: 3em;
                    margin-bottom: 20px;
                    text-shadow: 0 0 20px rgba(229,9,20,0.5);
                }
                p { color: #aaa; font-size: 1.2em; }
                .netflix-btn {
                    background: #E50914;
                    color: white;
                    border: none;
                    padding: 15px 40px;
                    font-size: 1.2em;
                    border-radius: 5px;
                    cursor: pointer;
                    margin-top: 30px;
                    text-decoration: none;
                    display: inline-block;
                }
                .netflix-btn:hover { background: #F6121D; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎬 Netflix Premium Bot</h1>
                <p>🔥 Ultimate Edition - Direct Login System</p>
                <br>
                <p>Use the Telegram bot to generate login links</p>
            </div>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')

    async def login_page(self, request):
        """Handle login token - redirect to Netflix or show cookie"""
        token = request.match_info.get('token', '')
        token_data = self.db.get_login_token(token)

        if not token_data:
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Link Expired</title>
                <style>
                    * { margin: 0; padding: 0; box-sizing: border-box; }
                    body {
                        background: #141414;
                        color: #fff;
                        font-family: 'Helvetica Neue', Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                    }
                    .container { text-align: center; padding: 40px; }
                    h1 { color: #E50914; font-size: 2.5em; margin-bottom: 20px; }
                    p { color: #aaa; font-size: 1.2em; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>❌ Link Expired</h1>
                    <p>This login link has expired or already been used.</p>
                    <p>Please generate a new one from the bot.</p>
                </div>
            </body>
            </html>
            """
            return web.Response(text=html, content_type='text/html')

        # Increment access count
        self.db.increment_token_access(token)

        cookie = token_data['cookie_data']

        # Build the login page with auto-set-cookie functionality
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Netflix Login</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    background: #141414;
                    color: #fff;
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    flex-direction: column;
                }}
                .container {{
                    text-align: center;
                    padding: 40px;
                    max-width: 600px;
                    width: 100%;
                }}
                h1 {{
                    color: #E50914;
                    font-size: 2.5em;
                    margin-bottom: 20px;
                    text-shadow: 0 0 30px rgba(229,9,20,0.5);
                }}
                .cookie-box {{
                    background: #1a1a2e;
                    border: 1px solid #E50914;
                    border-radius: 10px;
                    padding: 20px;
                    margin: 20px 0;
                    text-align: left;
                    word-break: break-all;
                    max-height: 200px;
                    overflow-y: auto;
                }}
                .cookie-box code {{
                    color: #00ff88;
                    font-size: 0.85em;
                    line-height: 1.5;
                }}
                .btn-group {{
                    display: flex;
                    gap: 15px;
                    justify-content: center;
                    flex-wrap: wrap;
                    margin-top: 25px;
                }}
                .netflix-btn {{
                    background: #E50914;
                    color: white;
                    border: none;
                    padding: 15px 30px;
                    font-size: 1.1em;
                    border-radius: 5px;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    transition: all 0.3s;
                }}
                .netflix-btn:hover {{ background: #F6121D; transform: scale(1.05); }}
                .copy-btn {{
                    background: #333;
                    color: white;
                    border: 1px solid #555;
                    padding: 15px 30px;
                    font-size: 1.1em;
                    border-radius: 5px;
                    cursor: pointer;
                    transition: all 0.3s;
                }}
                .copy-btn:hover {{ background: #444; }}
                .step {{
                    background: #1a1a2e;
                    border-radius: 8px;
                    padding: 15px;
                    margin: 10px 0;
                    text-align: left;
                    border-left: 3px solid #E50914;
                }}
                .step-num {{
                    color: #E50914;
                    font-weight: bold;
                    font-size: 1.2em;
                }}
                .timer {{
                    color: #E50914;
                    font-size: 1.5em;
                    margin-top: 20px;
                    font-weight: bold;
                }}
                .success-msg {{
                    color: #00ff88;
                    display: none;
                    margin-top: 10px;
                    font-size: 1.1em;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎬 Netflix Premium</h1>
                
                <div class="step">
                    <span class="step-num">Step 1:</span> Copy the cookie below
                </div>
                
                <div class="cookie-box">
                    <code id="cookieText">{cookie}</code>
                </div>
                
                <div class="btn-group">
                    <button class="copy-btn" onclick="copyCookie()">📋 Copy Cookie</button>
                    <a href="https://www.netflix.com" class="netflix-btn" target="_blank">🚀 Open Netflix</a>
                </div>
                
                <div class="success-msg" id="successMsg">✅ Cookie Copied!</div>
                
                <div class="step">
                    <span class="step-num">Step 2:</span> Install "EditThisCookie" or "Cookie-Editor" browser extension
                </div>
                
                <div class="step">
                    <span class="step-num">Step 3:</span> Go to netflix.com, paste the cookie in the extension, and refresh
                </div>
                
                <div class="step">
                    <span class="step-num">Alternative:</span> Click "Open Netflix" → Login will be automatic if cookie is active
                </div>
                
                <div class="timer" id="timer">⏰ Link expires in: --:--</div>
            </div>
            
            <script>
                function copyCookie() {{
                    const cookie = document.getElementById('cookieText').textContent;
                    navigator.clipboard.writeText(cookie).then(() => {{
                        document.getElementById('successMsg').style.display = 'block';
                        setTimeout(() => {{
                            document.getElementById('successMsg').style.display = 'none';
                        }}, 3000);
                    }}).catch(() => {{
                        // Fallback
                        const textarea = document.createElement('textarea');
                        textarea.value = cookie;
                        document.body.appendChild(textarea);
                        textarea.select();
                        document.execCommand('copy');
                        document.body.removeChild(textarea);
                        document.getElementById('successMsg').style.display = 'block';
                        setTimeout(() => {{
                            document.getElementById('successMsg').style.display = 'none';
                        }}, 3000);
                    }});
                }}
                
                // Timer countdown
                let expiry = new Date("{token_data['expires_at']}");
                function updateTimer() {{
                    let now = new Date();
                    let diff = expiry - now;
                    if (diff <= 0) {{
                        document.getElementById('timer').textContent = '❌ Link Expired';
                        return;
                    }}
                    let hours = Math.floor(diff / 3600000);
                    let mins = Math.floor((diff % 3600000) / 60000);
                    let secs = Math.floor((diff % 60000) / 1000);
                    document.getElementById('timer').textContent = 
                        '⏰ Link expires in: ' + hours + 'h ' + mins + 'm ' + secs + 's';
                }}
                setInterval(updateTimer, 1000);
                updateTimer();
            </script>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')

    async def get_cookie(self, request):
        """API endpoint to get cookie data as JSON"""
        token = request.match_info.get('token', '')
        token_data = self.db.get_login_token(token)

        if not token_data:
            return web.json_response({'error': 'Token expired or invalid'}, status=404)

        self.db.increment_token_access(token)

        return web.json_response({
            'cookie': token_data['cookie_data'],
            'account_id': token_data['account_id'],
            'expires_at': token_data['expires_at'],
        })

    async def health_check(self, request):
        """Health check endpoint"""
        return web.json_response({
            'status': 'ok',
            'version': BOT_VERSION,
            'accounts_available': self.db.get_account_count('available'),
        })

    def run(self):
        """Start the web server"""
        web.run_app(self.app, host=WEB_HOST, port=WEB_PORT, print=None)
