import numpy as np
import pandas as pd
import time
from dataclasses import dataclass
from typing import Tuple, Optional, Callable, Any, Dict
from enum import Enum
import pvlib
from pvlib import solarposition, irradiance, location

# 保留原有的枚举和配置类
class ControllerType(Enum):
    DIFFERENTIAL = "diff"
    PERTURB_OBSERVE = "po"
    OPTIMAL = "optimal"
    HYBRID = "hybrid"

@dataclass
class SimulationConfig:
    # 保留原有字段，但改为可选参数并有默认值
    latitude: float = 35.0
    longitude: float = 120.0
    panel_width: float = 2.0
    panel_height: float = 1.0
    sensor_offsets: Tuple[Tuple[float, float], ...] = ((-0.9, -0.45), (0.9, -0.45), (-0.9, 0.45), (0.9, 0.45))
    initial_tilt: float = 30.0
    initial_azimuth: float = 180.0
    max_angular_velocity: float = 2.0
    control_period: float = 5.0
    simulation_duration: float = 3600 * 4
    cloud_velocity: Tuple[float, float] = (0.5, 0.0)
    cloud_sigma: float = 200.0
    cloud_depth: float = 0.9
    sky_diffuse_floor: float = 50.0
    start_time: Optional[pd.Timestamp] = None
    timezone: str = 'Asia/Shanghai'
    panel_efficiency: float = 0.20
    controller_type: ControllerType = ControllerType.HYBRID

    def __post_init__(self):
        if self.start_time is None:
            self.start_time = pd.Timestamp('2024-06-15 08:00:00').tz_localize(self.timezone)
        # 确保controller_type是枚举类型
        if isinstance(self.controller_type, str):
            self.controller_type = ControllerType(self.controller_type)

# 保留原有的PanelState, PhotovoltaicPanel, CloudModel, SunModel, SensorModel和控制器类

class SimulationEngine:
    def __init__(self, config_data: Dict[str, Any] = None):
        if config_data is None:
            config_data = {}
        
        # 使用配置数据创建SimulationConfig实例
        self.config = SimulationConfig(**config_data)
        
        # 初始化组件
        self.panel = PhotovoltaicPanel(self.config)
        self.cloud_model = CloudModel(self.config)
        self.sun_model = SunModel(self.config)
        self.sensor_model = SensorModel(self.config)
        
        # 根据配置选择控制器
        if self.config.controller_type == ControllerType.DIFFERENTIAL:
            self.controller = DifferentialController(self.config)
        elif self.config.controller_type == ControllerType.PERTURB_OBSERVE:
            self.controller = POController(self.config)
        elif self.config.controller_type == ControllerType.OPTIMAL:
            self.controller = OptimalController(self.config)
        else:
            self.controller = HybridController(self.config)
        
        self.results = []
        self.is_running = False
        self.progress = 0.0
        
    def run(self, progress_callback: Optional[Callable] = None):
        self.is_running = True
        start_time = time.time()
        
        # 生成时间点
        times = np.arange(0.0, self.config.simulation_duration + 1e-6, self.config.control_period)
        total_steps = len(times)
        
        for i, t in enumerate(times):
            # 计算太阳位置
            sun_elev, sun_azi = self.sun_model.get_position(t)
            
            # 获取传感器读数
            sensor_readings = self.sensor_model.calculate_readings(
                self.panel, t, sun_elev, sun_azi, self.cloud_model
            )
            
            # 获取面板状态
            panel_state = self.panel.get_state()
            
            # 计算控制动作
            d_azi, d_tilt = self.controller.compute_control_action(
                sensor_readings, panel_state, sun_elev, sun_azi
            )
            
            # 更新面板角度
            self.panel.set_angle(panel_state.tilt + d_tilt, panel_state.azimuth + d_azi)
            
            # 更新云层
            self.cloud_model.update(self.config.control_period)
            
            # 计算晴空入射用于记录
            poa_dir, poa_dif, poa_glb = self.sun_model.get_irradiance(
                t, self.panel.tilt, self.panel.azimuth
            )
            
            # 保存结果
            result = {
                'time': t,
                'sun_elevation': np.degrees(sun_elev),
                'sun_azimuth': np.degrees(sun_azi),
                'panel_tilt': self.panel.tilt,
                'panel_azimuth': self.panel.azimuth,
                'sensor_readings': sensor_readings.tolist(),
                'total_irradiance': float(np.sum(sensor_readings)),
                'poa_dir': poa_dir,
                'poa_dif': poa_dif,
                'poa_glb': poa_glb,
                'delta_azimuth': d_azi,
                'delta_tilt': d_tilt,
                'cloud_cover': 1.0 - self.cloud_model.attenuation(np.array([0.0, 0.0])),
            }
            
            self.results.append(result)
            
            # 更新进度
            self.progress = (i + 1) / total_steps * 100
            
            # 每隔一定步骤或最后一步发送数据
            if progress_callback and (i % 10 == 0 or i == total_steps - 1):
                progress_callback({
                    'progress': self.progress,
                    'current_data': result,
                    'summary_stats': self.get_summary_stats()
                })
            
            # 添加短暂延迟以模拟实时效果（可选）
            # time.sleep(0.01)
        
        self.is_running = False
        print(f"Simulation completed in: {time.time() - start_time:.2f} seconds")
    
    def get_latest_results(self, n: int = 100):
        """获取最近n条结果"""
        if not self.results:
            return []
        return self.results[-n:]
    
    def get_summary_stats(self):
        """获取摘要统计信息"""
        if not self.results:
            return {}
        
        df = pd.DataFrame(self.results)
        return {
            'total_energy': float(df['total_irradiance'].sum()),
            'avg_efficiency': float(100.0 * df['total_irradiance'].mean() / df['poa_glb'].mean()),
            'max_irradiance': float(df['total_irradiance'].max()),
            'min_irradiance': float(df['total_irradiance'].min()),
        }

@dataclass
class PanelState:
    """Panel state"""
    tilt: float  # tilt angle (degrees)
    azimuth: float  # azimuth angle (degrees), 180 is south
    sensor_readings: np.ndarray  # readings from four sensors


class PhotovoltaicPanel:
    """Photovoltaic panel class"""
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.tilt = config.initial_tilt
        self.azimuth = config.initial_azimuth
        self.sensor_positions = np.array(config.sensor_offsets)
        
    def set_angle(self, tilt: float, azimuth: float):
        """Set panel angles"""
        self.tilt = np.clip(tilt, 0, 90)
        self.azimuth = azimuth % 360
        
    def get_state(self) -> PanelState:
        """Get current panel state"""
        return PanelState(self.tilt, self.azimuth, np.zeros(4))


class CloudModel:
    """Cloud model with multiple clouds"""
    def __init__(self, config: SimulationConfig):
        self.config = config
        # Multiple clouds for more realistic simulation
        self.clouds = [
            {'center': np.array([0.0, -500.0]), 'velocity': np.array([0.5, 0.0]), 'sigma': 200.0, 'depth': 0.9},
            {'center': np.array([300.0, -800.0]), 'velocity': np.array([0.3, 0.1]), 'sigma': 150.0, 'depth': 0.7},
            {'center': np.array([-200.0, -1200.0]), 'velocity': np.array([0.4, -0.1]), 'sigma': 250.0, 'depth': 0.8}
        ]
        
    def update(self, dt: float):
        """Update cloud positions"""
        for cloud in self.clouds:
            cloud['center'] += cloud['velocity'] * dt
        
    def attenuation(self, point: np.ndarray) -> float:
        """Calculate total cloud attenuation at a point (multiplicative)"""
        total_attenuation = 1.0
        for cloud in self.clouds:
            d = np.linalg.norm(point - cloud['center'])
            cloud_att = 1.0 - cloud['depth'] * np.exp(-0.5 * (d/cloud['sigma'])**2)
            total_attenuation *= cloud_att  # Multiply attenuation from multiple clouds
            
        return total_attenuation


class SunModel:
    """Sun model using PVLib for accurate position and irradiance"""
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.location = location.Location(
            config.latitude, config.longitude, tz=config.timezone
        )
        
    def get_position(self, t: float) -> Tuple[float, float]:
        """Get sun position (elevation and azimuth in radians) using PVLib"""
        current_time = self.config.start_time + pd.Timedelta(seconds=t)
        
        # Get solar position
        solpos = solarposition.get_solarposition(
            current_time, 
            self.config.latitude, 
            self.config.longitude
        )
        
        # Convert to radians
        zenith = np.radians(solpos['apparent_zenith'].iloc[0])
        azimuth = np.radians(solpos['azimuth'].iloc[0])
        elevation = np.pi/2 - zenith  # Convert to elevation
        
        return elevation, azimuth
    
    def get_irradiance(self, t: float, panel_tilt: float, panel_azimuth: float) -> Tuple[float, float, float]:
        """Get solar irradiance components using PVLib"""
        current_time = self.config.start_time + pd.Timedelta(seconds=t)
        times = pd.DatetimeIndex([current_time])
        
        # Get solar position
        solpos = solarposition.get_solarposition(
            times, 
            self.config.latitude, 
            self.config.longitude
        )
        
        # Get clear sky irradiance using simplified model
        # Create a simple clear sky model instead of using get_clearsky
        dni = self.config.direct_irradiance_base
        ghi = dni * np.sin(np.pi/2 - np.radians(solpos['apparent_zenith'].iloc[0])) + self.config.sky_diffuse
        dhi = self.config.sky_diffuse
        
        # Calculate plane of array irradiance
        poa = irradiance.get_total_irradiance(
            panel_tilt,
            panel_azimuth,
            solpos['apparent_zenith'],
            solpos['azimuth'],
            dni,
            ghi,
            dhi
        )
        
        return poa['poa_direct'].iloc[0], poa['poa_diffuse'].iloc[0], poa['poa_global'].iloc[0]
    
    def get_direct_irradiance_on_panel(self, t: float, panel_tilt: float, panel_azimuth: float) -> float:
        """Calculate direct irradiance on panel using simplified model"""
        current_time = self.config.start_time + pd.Timedelta(seconds=t)
        
        # Get solar position
        solpos = solarposition.get_solarposition(
            current_time, 
            self.config.latitude, 
            self.config.longitude
        )
        
        # Simplified direct irradiance calculation
        # Calculate the angle of incidence
        sun_elevation = np.pi/2 - np.radians(solpos['apparent_zenith'].iloc[0])
        sun_azimuth = np.radians(solpos['azimuth'].iloc[0])
        
        # Calculate the angle of incidence
        cos_incidence = (
            np.sin(np.radians(panel_tilt)) * np.sin(sun_elevation) * 
            np.cos(np.radians(panel_azimuth) - sun_azimuth) +
            np.cos(np.radians(panel_tilt)) * np.cos(sun_elevation)
        )
        
        # Direct irradiance on panel
        direct_irradiance = self.config.direct_irradiance_base * max(0, cos_incidence)
        
        return direct_irradiance


class SensorModel:
    """Advanced sensor model"""
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.sun_model = SunModel(config)
        
    def calculate_readings(self, panel: PhotovoltaicPanel, t: float, 
                          sun_elevation: float, sun_azimuth: float, 
                          cloud_model: CloudModel) -> np.ndarray:
        """Calculate sensor readings using simplified model"""
        readings = np.zeros(4)
        
        # Get direct irradiance on panel using simplified model
        direct_irradiance = self.sun_model.get_direct_irradiance_on_panel(
            t, panel.tilt, panel.azimuth
        )
        
        # Get diffuse irradiance (simplified model)
        diffuse_irradiance = self.config.sky_diffuse
        
        for i, sensor_pos in enumerate(panel.sensor_positions):
            # Calculate cloud attenuation
            att = cloud_model.attenuation(sensor_pos)
            
            # Total irradiance (direct attenuated by clouds + diffuse)
            total_irradiance = att * direct_irradiance + diffuse_irradiance
            
            # Add some noise
            noise = np.random.normal(0, 5)
            readings[i] = max(total_irradiance + noise, 0)
            
        return readings


class Controller:
    """Controller base class"""
    def __init__(self, config: SimulationConfig):
        self.config = config
        
    def compute_control_action(self, sensor_readings: np.ndarray, 
                              panel_state: PanelState, sun_elevation: float,
                              sun_azimuth: float) -> Tuple[float, float]:
        """Compute control action (return azimuth and tilt changes)"""
        raise NotImplementedError


class DifferentialController(Controller):
    """Differential controller with improved logic"""
    def __init__(self, config: SimulationConfig):
        super().__init__(config)
        self.integral_azimuth = 0
        self.integral_tilt = 0
        self.prev_error_azimuth = 0
        self.prev_error_tilt = 0
        
    def compute_control_action(self, sensor_readings: np.ndarray, 
                              panel_state: PanelState, sun_elevation: float,
                              sun_azimuth: float) -> Tuple[float, float]:
        # Calculate east-west difference (sensors 0 and 2 vs 1 and 3)
        left = sensor_readings[0] + sensor_readings[2]
        right = sensor_readings[1] + sensor_readings[3]
        
        # Calculate north-south difference (sensors 2 and 3 vs 0 and 1)
        top = sensor_readings[2] + sensor_readings[3]
        bottom = sensor_readings[0] + sensor_readings[1]
        
        # Calculate errors
        error_azimuth = left - right
        error_tilt = top - bottom
        
        # PID control for azimuth
        p_azimuth = 0.1 * error_azimuth
        self.integral_azimuth += 0.01 * error_azimuth
        d_azimuth = 0.05 * (error_azimuth - self.prev_error_azimuth)
        delta_azimuth = p_azimuth + self.integral_azimuth + d_azimuth
        self.prev_error_azimuth = error_azimuth
        
        # PID control for tilt
        p_tilt = 0.1 * error_tilt
        self.integral_tilt += 0.01 * error_tilt
        d_tilt = 0.05 * (error_tilt - self.prev_error_tilt)
        delta_tilt = p_tilt + self.integral_tilt + d_tilt
        self.prev_error_tilt = error_tilt
        
        # Apply limits
        delta_azimuth = np.clip(delta_azimuth, -self.config.max_angular_velocity, self.config.max_angular_velocity)
        delta_tilt = np.clip(delta_tilt, -self.config.max_angular_velocity, self.config.max_angular_velocity)
        
        return delta_azimuth, delta_tilt


class POController(Controller):
    """Improved Perturb and Observe controller"""
    def __init__(self, config: SimulationConfig):
        super().__init__(config)
        self.prev_total = 0
        self.perturbation_magnitude = 0.5  # degrees
        self.azimuth_direction = 1
        self.tilt_direction = 1
        self.perturb_count = 0
        
    def compute_control_action(self, sensor_readings: np.ndarray, 
                              panel_state: PanelState, sun_elevation: float,
                              sun_azimuth: float) -> Tuple[float, float]:
        current_total = np.sum(sensor_readings)
        
        # First run, just record no action
        if self.prev_total == 0:
            self.prev_total = current_total
            return 0, 0
        
        # Determine perturbation direction
        if current_total > self.prev_total:
            # Keep same direction
            pass
        else:
            # Change direction
            if self.perturb_count % 2 == 0:
                self.azimuth_direction *= -1
            else:
                self.tilt_direction *= -1
                
        # Apply perturbation
        delta_azimuth = self.azimuth_direction * self.perturbation_magnitude
        delta_tilt = self.tilt_direction * self.perturbation_magnitude
        
        # Update history
        self.prev_total = current_total
        self.perturb_count += 1
        
        return delta_azimuth, delta_tilt


class OptimalController(Controller):
    """Optimal controller that uses sun position for optimal tracking"""
    def __init__(self, config: SimulationConfig):
        super().__init__(config)
        
    def compute_control_action(self, sensor_readings: np.ndarray, 
                              panel_state: PanelState, sun_elevation: float,
                              sun_azimuth: float) -> Tuple[float, float]:
        # Calculate optimal angles based on sun position
        optimal_tilt = np.degrees(np.pi/2 - sun_elevation)
        optimal_azimuth = np.degrees(sun_azimuth)
        
        # Calculate errors
        error_tilt = optimal_tilt - panel_state.tilt
        error_azimuth = optimal_azimuth - panel_state.azimuth
        
        # Normalize azimuth error
        if error_azimuth > 180:
            error_azimuth -= 360
        elif error_azimuth < -180:
            error_azimuth += 360
            
        # Apply control with limits
        delta_tilt = np.clip(error_tilt * 0.1, -self.config.max_angular_velocity, self.config.max_angular_velocity)
        delta_azimuth = np.clip(error_azimuth * 0.1, -self.config.max_angular_velocity, self.config.max_angular_velocity)
        
        return delta_azimuth, delta_tilt


class HybridController(Controller):
    """Hybrid controller that combines optimal and differential approaches"""
    def __init__(self, config: SimulationConfig):
        super().__init__(config)
        self.optimal_controller = OptimalController(config)
        self.differential_controller = DifferentialController(config)
        self.mode = "optimal"  # Start with optimal mode
        
    def compute_control_action(self, sensor_readings: np.ndarray, 
                              panel_state: PanelState, sun_elevation: float,
                              sun_azimuth: float) -> Tuple[float, float]:
        # Check if there's significant cloud cover (large differences between sensors)
        sensor_variance = np.var(sensor_readings)
        
        # Switch mode based on conditions
        if sensor_variance > 100:  # High variance indicates cloud cover
            self.mode = "differential"
        else:
            self.mode = "optimal"
            
        # Use appropriate controller
        if self.mode == "optimal":
            return self.optimal_controller.compute_control_action(
                sensor_readings, panel_state, sun_elevation, sun_azimuth
            )
        else:
            return self.differential_controller.compute_control_action(
                sensor_readings, panel_state, sun_elevation, sun_azimuth
            )
