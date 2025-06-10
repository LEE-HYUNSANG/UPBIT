from flask_socketio import SocketIO

# SocketIO instance to be shared across modules
socketio = SocketIO(cors_allowed_origins="*")
