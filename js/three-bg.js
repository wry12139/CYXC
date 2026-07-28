/**
 * Three.js 3D 背景系统
 * 为每个 Section 创建独特的 3D 背景效果
 */

let scene, camera, renderer, canvas;
let sections = {};
let animationId = null;
let isMobile = window.innerWidth < 768;
let qualityLevel = isMobile ? 'low' : 'high';

// 质量配置
const QUALITY_CONFIG = {
  high: { particleCount: 2000, triangles: 5000 },
  medium: { particleCount: 1000, triangles: 2500 },
  low: { particleCount: 300, triangles: 500 }
};

export function initThreeBg() {
  canvas = document.getElementById('bg-canvas');
  if (!canvas) return;

  // 检测设备能力
  detectQualityLevel();

  // 初始化 Three.js
  const width = window.innerWidth;
  const height = window.innerHeight;

  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
  camera.position.z = 5;

  renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    powerPreference: isMobile ? 'low-power' : 'high-performance'
  });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);

  // 创建各 Section 的 3D 背景
  createSection1Background();
  createSection2Background();
  createSection3Background();

  // 事件监听
  window.addEventListener('resize', onWindowResize);
  document.addEventListener('mousemove', onMouseMove);

  // 启动渲染循环
  animate();
}

function detectQualityLevel() {
  // 检测 GPU 能力
  const canvas = document.createElement('canvas');
  const gl = canvas.getContext('webgl');
  const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
  const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);

  // 简单的设备检测
  if (isMobile) {
    qualityLevel = 'low';
  } else if (renderer.includes('Intel') || renderer.includes('AMD')) {
    qualityLevel = 'medium';
  } else {
    qualityLevel = 'high';
  }
}

function createSection1Background() {
  const group = new THREE.Group();
  scene.add(group);
  sections.section1 = { group, objects: [] };

  // 创建旋转立方体
  const cubeGeometry = new THREE.BoxGeometry(2, 2, 2);
  const cubeMaterial = new THREE.MeshPhongMaterial({
    color: 0x667eea,
    emissive: 0x667eea,
    emissiveIntensity: 0.3,
    wireframe: false
  });
  const cube = new THREE.Mesh(cubeGeometry, cubeMaterial);
  cube.rotation.x = 0.3;
  cube.rotation.y = 0.4;
  group.add(cube);
  sections.section1.objects.push({ mesh: cube, rotationSpeed: { x: 0.002, y: 0.001 } });

  // 添加光线
  const lightGeometry = new THREE.IcosahedronGeometry(3, 4);
  const lightMaterial = new THREE.MeshPhongMaterial({
    color: 0x764ba2,
    emissive: 0x764ba2,
    emissiveIntensity: 0.2,
    wireframe: true
  });
  const light = new THREE.Mesh(lightGeometry, lightMaterial);
  light.scale.set(0.8, 0.8, 0.8);
  group.add(light);
  sections.section1.objects.push({ mesh: light, rotationSpeed: { x: -0.001, y: -0.002 } });

  // 创建浮动粒子
  if (qualityLevel !== 'low') {
    createFloatingParticles(group, 1500);
  }

  // 灯光
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
  group.add(ambientLight);

  const pointLight = new THREE.PointLight(0x667eea, 1);
  pointLight.position.set(5, 5, 5);
  group.add(pointLight);

  const pointLight2 = new THREE.PointLight(0x764ba2, 0.8);
  pointLight2.position.set(-5, -5, 5);
  group.add(pointLight2);
}

function createSection2Background() {
  const group = new THREE.Group();
  scene.add(group);
  sections.section2 = { group, objects: [] };

  // 创建粒子网络（知识连接）
  const particleCount = QUALITY_CONFIG[qualityLevel].particleCount;
  const particles = new THREE.BufferGeometry();
  const positions = [];

  for (let i = 0; i < particleCount; i++) {
    positions.push(
      (Math.random() - 0.5) * 20,
      (Math.random() - 0.5) * 20,
      (Math.random() - 0.5) * 20
    );
  }

  particles.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));

  const pointsMaterial = new THREE.PointsMaterial({
    color: 0x667eea,
    size: 0.1,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.6
  });

  const points = new THREE.Points(particles, pointsMaterial);
  group.add(points);
  sections.section2.objects.push({ mesh: points, type: 'particle' });

  // 连线效果
  if (qualityLevel === 'high') {
    createParticleConnections(group, positions);
  }

  // 灯光
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
  group.add(ambientLight);

  const pointLight = new THREE.PointLight(0x667eea, 0.8);
  pointLight.position.set(10, 10, 10);
  group.add(pointLight);
}

function createSection3Background() {
  const group = new THREE.Group();
  scene.add(group);
  sections.section3 = { group, objects: [] };

  // 创建流动粒子系统
  const particleCount = QUALITY_CONFIG[qualityLevel].particleCount;
  const particles = new THREE.BufferGeometry();
  const positions = [];
  const velocities = [];

  for (let i = 0; i < particleCount; i++) {
    positions.push(
      (Math.random() - 0.5) * 15,
      (Math.random() - 0.5) * 15,
      (Math.random() - 0.5) * 15
    );
    velocities.push(
      (Math.random() - 0.5) * 0.02,
      (Math.random() - 0.5) * 0.05,
      (Math.random() - 0.5) * 0.02
    );
  }

  particles.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));

  const pointsMaterial = new THREE.PointsMaterial({
    color: 0x764ba2,
    size: 0.15,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.7
  });

  const points = new THREE.Points(particles, pointsMaterial);
  group.add(points);
  sections.section3.objects.push({
    mesh: points,
    type: 'flowing',
    velocities: velocities
  });

  // 灯光
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
  group.add(ambientLight);

  const pointLight = new THREE.PointLight(0x764ba2, 0.8);
  pointLight.position.set(-10, 10, 10);
  group.add(pointLight);
}

function createFloatingParticles(group, count) {
  const geometry = new THREE.BufferGeometry();
  const positions = [];

  for (let i = 0; i < count; i++) {
    positions.push(
      (Math.random() - 0.5) * 30,
      (Math.random() - 0.5) * 30,
      (Math.random() - 0.5) * 30
    );
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));

  const material = new THREE.PointsMaterial({
    color: 0xffffff,
    size: 0.02,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.3
  });

  const points = new THREE.Points(geometry, material);
  group.add(points);

  return { mesh: points, floatSpeed: 0.001 };
}

function createParticleConnections(group, positions) {
  const lines = [];
  const lineGeometry = new THREE.BufferGeometry();

  for (let i = 0; i < Math.min(positions.length / 3, 100); i++) {
    for (let j = i + 1; j < Math.min(positions.length / 3, 100); j++) {
      const dist = Math.hypot(
        positions[i * 3] - positions[j * 3],
        positions[i * 3 + 1] - positions[j * 3 + 1],
        positions[i * 3 + 2] - positions[j * 3 + 2]
      );

      if (dist < 8) {
        lines.push(i * 3, j * 3);
      }
    }
  }

  if (lines.length > 0) {
    const lineMaterial = new THREE.LineBasicMaterial({
      color: 0x667eea,
      transparent: true,
      opacity: 0.2,
      linewidth: 1
    });

    const lineSegments = new THREE.LineSegments(lineGeometry, lineMaterial);
    group.add(lineSegments);
  }
}

function onMouseMove(event) {
  if (isMobile) return;

  const x = (event.clientX / window.innerWidth) * 2 - 1;
  const y = -(event.clientY / window.innerHeight) * 2 + 1;

  // 微调相机位置
  camera.position.x += (x * 0.1 - camera.position.x) * 0.05;
  camera.position.y += (y * 0.1 - camera.position.y) * 0.05;
  camera.lookAt(0, 0, 0);
}

function animate() {
  animationId = requestAnimationFrame(animate);

  // 更新各 Section 的对象
  Object.values(sections).forEach((section) => {
    section.objects.forEach((obj) => {
      if (obj.type === 'particle') {
        // 粒子自旋
        obj.mesh.rotation.x += 0.0001;
        obj.mesh.rotation.y += 0.0002;
      } else if (obj.type === 'flowing') {
        // 流动粒子
        const pos = obj.mesh.geometry.attributes.position.array;
        for (let i = 0; i < pos.length; i += 3) {
          pos[i] += obj.velocities[i / 3 * 3] * 0.5;
          pos[i + 1] += obj.velocities[i / 3 * 3 + 1] * 0.5;
          pos[i + 2] += obj.velocities[i / 3 * 3 + 2] * 0.5;

          // 边界反弹
          if (Math.abs(pos[i]) > 10) obj.velocities[i / 3 * 3] *= -1;
          if (Math.abs(pos[i + 1]) > 10) obj.velocities[i / 3 * 3 + 1] *= -1;
          if (Math.abs(pos[i + 2]) > 10) obj.velocities[i / 3 * 3 + 2] *= -1;
        }
        obj.mesh.geometry.attributes.position.needsUpdate = true;
      } else if (obj.rotationSpeed) {
        // 旋转对象
        obj.mesh.rotation.x += obj.rotationSpeed.x;
        obj.mesh.rotation.y += obj.rotationSpeed.y;
      }
    });
  });

  renderer.render(scene, camera);
}

function onWindowResize() {
  const width = window.innerWidth;
  const height = window.innerHeight;

  camera.aspect = width / height;
  camera.updateProjectionMatrix();

  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  isMobile = width < 768;
}

export function stopThreeBg() {
  if (animationId) {
    cancelAnimationFrame(animationId);
  }
  window.removeEventListener('resize', onWindowResize);
  document.removeEventListener('mousemove', onMouseMove);
}
