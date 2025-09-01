class PVVisualization {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        
        // 初始化Three.js场景
        this.initScene();
        
        // 创建太阳能板模型
        this.createPanel();
        
        // 创建太阳和云模型
        this.createSun();
        this.createClouds();
        
        // 开始动画循环
        this.animate();
        
        // 初始视角控制
        this.camera.position.set(5, 5, 5);
        this.camera.lookAt(0, 0, 0);
    }
    
    initScene() {
        // 场景
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x87CEEB); // 天空蓝
        
        // 相机
        const aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 1000);
        
        // 渲染器
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.container.appendChild(this.renderer.domElement);
        
        // 光源
        const ambientLight = new THREE.AmbientLight(0x404040);
        this.scene.add(ambientLight);
        
        // 太阳光
        this.sunLight = new THREE.DirectionalLight(0xffffff, 1);
        this.sunLight.position.set(10, 10, 10);
        this.scene.add(this.sunLight);
        
        // 网格地面
        const gridHelper = new THREE.GridHelper(10, 10);
        this.scene.add(gridHelper);
        
        // 坐标轴
        const axesHelper = new THREE.AxesHelper(2);
        this.scene.add(axesHelper);
        
        // 窗口大小调整处理
        window.addEventListener('resize', () => this.onWindowResize());
    }
    
    createPanel() {
        // 创建太阳能板
        const panelGeometry = new THREE.BoxGeometry(2, 0.1, 1);
        const panelMaterial = new THREE.MeshPhongMaterial({ 
            color: 0x3366CC,
            transparent: true,
            opacity: 0.8
        });
        
        this.panel = new THREE.Mesh(panelGeometry, panelMaterial);
        this.scene.add(this.panel);
        
        // 创建四个传感器
        this.sensors = [];
        const sensorGeometry = new THREE.SphereGeometry(0.05, 16, 16);
        const sensorMaterial = new THREE.MeshBasicMaterial({ color: 0xFF0000 });
        
        // 传感器位置（相对于面板中心）
        const sensorPositions = [
            new THREE.Vector3(-0.9, 0.05, -0.45), // 左下
            new THREE.Vector3(0.9, 0.05, -0.45),  // 右下
            new THREE.Vector3(-0.9, 0.05, 0.45),  // 左上
            new THREE.Vector3(0.9, 0.05, 0.45)    // 右上
        ];
        
        sensorPositions.forEach(pos => {
            const sensor = new THREE.Mesh(sensorGeometry, sensorMaterial);
            sensor.position.copy(pos);
            this.panel.add(sensor);
            this.sensors.push(sensor);
        });
    }
    
    createSun() {
        const sunGeometry = new THREE.SphereGeometry(0.3, 32, 32);
        const sunMaterial = new THREE.MeshBasicMaterial({ 
            color: 0xFFFF00,
            emissive: 0xFFFF00,
            emissiveIntensity: 0.5
        });
        
        this.sun = new THREE.Mesh(sunGeometry, sunMaterial);
        this.scene.add(this.sun);
    }
    
    createClouds() {
        // 创建一些云团
        this.clouds = [];
        
        for (let i = 0; i < 3; i++) {
            const cloudGroup = new THREE.Group();
            
            // 创建由多个球体组成的云
            for (let j = 0; j < 5; j++) {
                const size = 0.2 + Math.random() * 0.2;
                const cloudPart = new THREE.Mesh(
                    new THREE.SphereGeometry(size, 16, 16),
                    new THREE.MeshPhongMaterial({
                        color: 0xFFFFFF,
                        transparent: true,
                        opacity: 0.7
                    })
                );
                
                cloudPart.position.set(
                    (Math.random() - 0.5) * 0.8,
                    (Math.random() - 0.5) * 0.3,
                    (Math.random() - 0.5) * 0.8
                );
                
                cloudGroup.add(cloudPart);
            }
            
            // 设置云的初始位置
            cloudGroup.position.set(
                (Math.random() - 0.5) * 10,
                2 + Math.random() * 2,
                (Math.random() - 0.5) * 10
            );
            
            this.scene.add(cloudGroup);
            this.clouds.push(cloudGroup);
        }
    }
    
    updatePanelOrientation(tilt, azimuth) {
        // 更新面板方向
        // 注意：Three.js中使用弧度，且坐标系可能与仿真不同
        this.panel.rotation.x = THREE.MathUtils.degToRad(tilt);
        this.panel.rotation.y = THREE.MathUtils.degToRad(azimuth - 180); // 调整坐标系
    }
    
    updateSunPosition(elevation, azimuth) {
        // 根据太阳高度角和方位角更新太阳位置
        const distance = 10; // 太阳距离
        
        // 将球坐标转换为直角坐标
        const phi = THREE.MathUtils.degToRad(90 - elevation); // 极角
        const theta = THREE.MathUtils.degToRad(azimuth); // 方位角
        
        this.sun.position.set(
            distance * Math.sin(phi) * Math.cos(theta),
            distance * Math.cos(phi),
            distance * Math.sin(phi) * Math.sin(theta)
        );
        
        // 更新阳光方向
        this.sunLight.position.copy(this.sun.position);
    }
    
    updateSensorReadings(readings) {
        // 根据传感器读数更新传感器外观（例如颜色）
        readings.forEach((value, index) => {
            // 将读数映射到颜色（从红到绿）
            const intensity = Math.min(value / 1000, 1); // 假设最大读数为1000
            this.sensors[index].material.color.setRGB(
                1 - intensity, 
                intensity, 
                0
            );
        });
    }
    
    updateClouds(cloudData) {
        // 更新云的位置和透明度（简化版本）
        // 实际应用中应根据仿真数据更新
        this.clouds.forEach((cloud, index) => {
            // 简单移动云
            cloud.position.x += 0.01;
            if (cloud.position.x > 5) cloud.position.x = -5;
            
            // 根据云覆盖数据调整透明度
            if (cloudData && index < cloudData.length) {
                const opacity = 0.3 + cloudData[index].opacity * 0.7;
                cloud.children.forEach(part => {
                    part.material.opacity = opacity;
                });
            }
        });
    }
    
    onWindowResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());
        this.renderer.render(this.scene, this.camera);
    }
    
    // 从仿真数据更新可视化
    updateFromData(data) {
        if (data.panel_tilt !== undefined && data.panel_azimuth !== undefined) {
            this.updatePanelOrientation(data.panel_tilt, data.panel_azimuth);
        }
        
        if (data.sun_elevation !== undefined && data.sun_azimuth !== undefined) {
            this.updateSunPosition(data.sun_elevation, data.sun_azimuth);
        }
        
        if (data.sensor_readings) {
            this.updateSensorReadings(data.sensor_readings);
        }
        
        this.updateClouds(); // 实际应用中应传递云数据
    }
}

// 初始化可视化
let pvVisualization = null;
document.addEventListener('DOMContentLoaded', () => {
    pvVisualization = new PVVisualization('threejs-canvas');
});
