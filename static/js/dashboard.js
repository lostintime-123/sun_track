// 全局变量
let socket = null;
let charts = {};
let simulationData = [];

// 初始化Socket.io连接
function initSocket() {
    socket = io();
    
    socket.on('connect', () => {
        console.log('Connected to server');
        updateStatus('Connected to server');
    });
    
    socket.on('simulation_data', (data) => {
        handleSimulationData(data);
    });
    
    socket.on('simulation_complete', (data) => {
        updateStatus('Simulation completed');
        document.getElementById('start-btn').disabled = false;
        document.getElementById('pause-btn').disabled = true;
    });
    
    socket.on('disconnect', () => {
        updateStatus('Disconnected from server');
    });
}

// 初始化图表
function initCharts() {
    // 辐照度图表
    charts.irradiance = Plotly.newPlot('irradiance-chart', [{
        x: [],
        y: [],
        type: 'scatter',
        name: 'Total Irradiance'
    }, {
        x: [],
        y: [],
        type: 'scatter',
        name: 'Theoretical Maximum',
        line: { dash: 'dot' }
    }], {
        title: 'Irradiance Over Time',
        xaxis: { title: 'Time (min)' },
        yaxis: { title: 'Irradiance (W/m²)' }
    });
    
    // 角度图表
    charts.angles = Plotly.newPlot('angles-chart', [{
        x: [],
        y: [],
        type: 'scatter',
        name: 'Panel Tilt'
    }, {
        x: [],
        y: [],
        type: 'scatter',
        name: 'Panel Azimuth'
    }, {
        x: [],
        y: [],
        type: 'scatter',
        name: 'Sun Elevation',
        line: { dash: 'dot' }
    }], {
        title: 'Angles Over Time',
        xaxis: { title: 'Time (min)' },
        yaxis: { title: 'Angle (deg)' }
    });
    
    // 传感器图表
    charts.sensors = Plotly.newPlot('sensors-chart', [
        { x: [], y: [], type: 'scatter', name: 'Sensor 1' },
        { x: [], y: [], type: 'scatter', name: 'Sensor 2' },
        { x: [], y: [], type: 'scatter', name: 'Sensor 3' },
        { x: [], y: [], type: 'scatter', name: 'Sensor 4' }
    ], {
        title: 'Sensor Readings Over Time',
        xaxis: { title: 'Time (min)' },
        yaxis: { title: 'Irradiance (W/m²)' }
    });
    
    // 效率图表
    charts.efficiency = Plotly.newPlot('efficiency-chart', [{
        x: [],
        y: [],
        type: 'scatter',
        name: 'Efficiency'
    }], {
        title: 'System Efficiency Over Time',
        xaxis: { title: 'Time (min)' },
        yaxis: { title: 'Efficiency (%)' }
    });
}

// 处理仿真数据
function handleSimulationData(data) {
    // 更新进度条
    updateProgress(data.progress);
    
    // 更新摘要统计
    if (data.summary_stats) {
        updateSummaryStats(data.summary_stats);
    }
    
    // 更新当前数据
    if (data.current_data) {
        simulationData.push(data.current_data);
        
        // 更新Three.js可视化
        if (pvVisualization) {
            pvVisualization.updateFromData(data.current_data);
        }
        
        // 更新图表
        updateCharts(data.current_data);
    }
}

// 更新图表数据
function updateCharts(data) {
    const timeMin = data.time / 60;
    
    // 更新辐照度图表
    Plotly.extendTraces('irradiance-chart', {
        x: [[timeMin], [timeMin]],
        y: [[data.total_irradiance], [data.poa_glb]]
    }, [0, 1]);
    
    // 更新角度图表
    Plotly.extendTraces('angles-chart', {
        x: [[timeMin], [timeMin], [timeMin]],
        y: [[data.panel_tilt], [data.panel_azimuth], [data.sun_elevation]]
    }, [0, 1, 2]);
    
    // 更新传感器图表
    Plotly.extendTraces('sensors-chart', {
        x: [
            [timeMin], [timeMin], [timeMin], [timeMin]
        ],
        y: [
            [data.sensor_readings[0]],
            [data.sensor_readings[1]],
            [data.sensor_readings[2]],
            [data.sensor_readings[3]]
        ]
    }, [0, 1, 2, 3]);
    
    // 更新效率图表
    const efficiency = 100.0 * data.total_irradiance / data.poa_glb;
    Plotly.extendTraces('efficiency-chart', {
        x: [[timeMin]],
        y: [[efficiency]]
    }, [0]);
}

// 启动仿真
function startSimulation() {
    const preset = document.getElementById('config-preset').value;
    let config = {};
    
    if (preset === 'custom') {
        // 从表单收集自定义配置
        config = {
            latitude: parseFloat(document.getElementById('latitude').value),
            longitude: parseFloat(document.getElementById('longitude').value),
            controller_type: document.getElementById('controller-type').value
            // 收集其他配置字段...
        };
    } else {
        // 使用预设配置
        fetch('/api/config/presets')
            .then(response => response.json())
            .then(presets => {
                config = presets[preset];
                sendStartRequest(config);
            });
        return;
    }
    
    sendStartRequest(config);
}

function sendStartRequest(config) {
    // 发送启动请求
    fetch('/api/simulation/start', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ config: config })
    })
    .then(response => response.json())
    .then(data => {
        updateStatus('Simulation started');
        document.getElementById('start-btn').disabled = true;
        document.getElementById('pause-btn').disabled = false;
        
        // 重置图表
        resetCharts();
    })
    .catch(error => {
        console.error('Error starting simulation:', error);
        updateStatus('Error starting simulation');
    });
}

// 暂停仿真
function pauseSimulation() {
    // 实现暂停逻辑
    updateStatus('Simulation paused');
    document.getElementById('start-btn').disabled = false;
    document.getElementById('pause-btn').disabled = true;
}

// 重置仿真
function resetSimulation() {
    // 实现重置逻辑
    simulationData = [];
    resetCharts();
    updateStatus('Simulation reset');
    updateProgress(0);
    updateSummaryStats({});
}

// 重置图表
function resetCharts() {
    for (const chartId in charts) {
        Plotly.deleteTraces(chartId, [...Array(charts[chartId].data.length).keys()]);
    }
}

// 更新状态显示
function updateStatus(message) {
    document.getElementById('status').textContent = message;
}

// 更新进度条
function updateProgress(percent) {
    const progressBar = document.getElementById('progress');
    progressBar.style.width = `${percent}%`;
    progressBar.textContent = `${percent.toFixed(1)}%`;
}

// 更新摘要统计
function updateSummaryStats(stats) {
    let html = '';
    for (const [key, value] of Object.entries(stats)) {
        html += `<div>${key}: ${value.toFixed(2)}</div>`;
    }
    document.getElementById('summary-stats').innerHTML = html;
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    initSocket();
    initCharts();
    
    // 配置预设更改事件
    document.getElementById('config-preset').addEventListener('change', function() {
        document.getElementById('custom-config').style.display = 
            this.value === 'custom' ? 'block' : 'none';
    });
});
