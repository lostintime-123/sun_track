# render修改
import os
import eventlet
eventlet.monkey_patch()



from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO
from simulation_engine import SimulationEngine
import json
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# 全局仿真引擎实例
sim_engine = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/simulation/start', methods=['POST'])
def start_simulation():
    global sim_engine
    config_data = request.json.get('config', {})
    
    # 创建仿真引擎
    sim_engine = SimulationEngine(config_data)
    
    # 启动仿真（在后台线程中运行）
    socketio.start_background_task(target=run_simulation)
    
    return jsonify({"status": "started", "message": "Simulation started"})

@app.route('/api/simulation/status')
def simulation_status():
    if sim_engine and sim_engine.is_running:
        return jsonify({"status": "running", "progress": sim_engine.progress})
    return jsonify({"status": "stopped"})

@app.route('/api/simulation/results')
def get_results():
    if sim_engine and sim_engine.results:
        # 返回最新结果
        return jsonify(sim_engine.get_latest_results())
    return jsonify({"error": "No results available"})

@app.route('/api/config/presets')
def get_config_presets():
    # 返回预定义的配置预设
    presets = {
        "default": {
            "latitude": 35.0,
            "longitude": 120.0,
            "simulation_duration": 3600 * 4,
            "controller_type": "hybrid"
        },
        "cloudy_day": {
            "latitude": 35.0,
            "longitude": 120.0,
            "simulation_duration": 3600 * 4,
            "cloud_depth": 0.95,
            "controller_type": "diff"
        }
    }
    return jsonify(presets)

def run_simulation():
    """在后台线程中运行仿真并发送实时数据"""
    if sim_engine:
        # 设置回调函数用于发送实时数据
        def progress_callback(data):
            socketio.emit('simulation_data', data)
        
        sim_engine.run(progress_callback=progress_callback)
        socketio.emit('simulation_complete', {"message": "Simulation completed"})

# if __name__ == '__main__':
#     socketio.run(app, debug=True, host='0.0.0.0', port=5000)

# 使用 Render 提供的 PORT 环境变量
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting server on port {port}")
    socketio.run(app, host='0.0.0.0', port=port)
