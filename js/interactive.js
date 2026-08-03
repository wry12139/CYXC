/**
 * 交互增强系统
 * 处理鼠标事件、响应式检测、性能优化
 */

let isMobileDevice = window.innerWidth < 768;
let isTablet = window.innerWidth >= 768 && window.innerWidth < 1024;
let lenisInstance = null;

export function initInteractiveFeatures() {
  // 监听窗口大小变化
  window.addEventListener('resize', debounce(onWindowResize, 300));

  // 响应式检测
  detectDeviceType();

  // 初始化平滑滚动
  initSmoothScrolling();

  // 初始化锚点平滑跳转
  initAnchorScrolling();

  // 初始化返回顶部按钮
  initBackToTopButton();

  // 初始化触摸优化
  if (isMobileDevice) {
    initTouchOptimizations();
  }

  // 性能监控
  initPerformanceMonitoring();
}

/**
 * 防抖函数
 */
function debounce(func, delay) {
  let timeoutId;
  return function (...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func(...args), delay);
  };
}

/**
 * 设备类型检测
 */
function detectDeviceType() {
  const width = window.innerWidth;
  isMobileDevice = width < 768;
  isTablet = width >= 768 && width < 1024;

  // 根据设备类型调整 Three.js 质量
  const event = new CustomEvent('deviceTypeChanged', {
    detail: { isMobile: isMobileDevice, isTablet }
  });
  window.dispatchEvent(event);
}

/**
 * 窗口大小变化处理
 */
function onWindowResize() {
  const oldIsMobile = isMobileDevice;
  detectDeviceType();

  if (oldIsMobile !== isMobileDevice) {
    // 设备类型改变了
    location.reload(); // 可选：重新加载优化性能
  }
}

/**
 * 平滑滚动（Lenis 或 GSAP 备选方案）
 */
function initSmoothScrolling() {
  // 检测 Lenis 库是否可用
  if (typeof Lenis !== 'undefined') {
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      direction: 'vertical',
      gestureDirection: 'vertical',
      smooth: true,
      mouseMultiplier: 1,
      smoothTouch: false,
      touchMultiplier: 2,
      infinite: false
    });

    lenisInstance = lenis;

    function raf(time) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);
  } else {
    // GSAP 的平滑滚动作为备选方案
    gsap.registerPlugin(ScrollToPlugin);
  }
}

/**
 * 锚点平滑跳转（导航、按钮、滚动提示）
 */
function initAnchorScrolling() {
  if (typeof gsap !== 'undefined' && gsap.registerPlugin && typeof ScrollToPlugin !== 'undefined') {
    gsap.registerPlugin(ScrollToPlugin);
  }

  const anchors = document.querySelectorAll('a[href^="#"]');

  anchors.forEach((anchor) => {
    anchor.addEventListener('click', (e) => {
      const href = anchor.getAttribute('href');
      if (!href || href === '#') return;

      const target = document.querySelector(href);
      if (!target) return;

      e.preventDefault();
      scrollToElement(target);
    });
  });
}

/**
 * 统一的平滑滚动到元素（优先 Lenis，其次 GSAP，最后原生）
 */
function scrollToElement(target) {
  if (lenisInstance) {
    lenisInstance.scrollTo(target, {
      duration: 1.4,
      easing: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)
    });
  } else if (typeof gsap !== 'undefined') {
    gsap.to(window, {
      duration: 1.4,
      scrollTo: { y: target, autoKill: false },
      ease: 'power2.inOut'
    });
  } else {
    target.scrollIntoView({ behavior: 'smooth' });
  }
}

/**
 * 返回顶部按钮优化
 */
function initBackToTopButton() {
  const backToTopBtn = document.querySelector('button');

  if (!backToTopBtn) return;

  // 改进返回顶部的触发条件
  let lastScrollTime = 0;
  const scrollHandler = debounce(() => {
    const scrollY = window.scrollY;

    if (scrollY > 300) {
      gsap.to(backToTopBtn, {
        duration: 0.3,
        opacity: 1,
        pointerEvents: 'auto',
        ease: 'power2.out'
      });
    } else {
      gsap.to(backToTopBtn, {
        duration: 0.3,
        opacity: 0,
        pointerEvents: 'none',
        ease: 'power2.out'
      });
    }
  }, 50);

  window.addEventListener('scroll', scrollHandler);

  // 优化点击处理
  backToTopBtn.addEventListener('click', (e) => {
    e.preventDefault();

    if (lenisInstance) {
      lenisInstance.scrollTo(0, {
        duration: 1.4,
        easing: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)
      });
    } else if (typeof gsap !== 'undefined') {
      gsap.to(window, {
        duration: 1.5,
        scrollTo: 0,
        ease: 'power2.inOut'
      });
    } else {
      window.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    }
  });

  // 初始状态隐藏
  gsap.set(backToTopBtn, {
    opacity: 0,
    pointerEvents: 'none'
  });
}

/**
 * 触摸设备优化
 */
function initTouchOptimizations() {
  // 移除 3D 悬停效果在移动设备上的 transform
  const cards = document.querySelectorAll('.card, .project-card');

  cards.forEach((card) => {
    card.addEventListener('touchstart', () => {
      // 触摸时保持简单的动画
      gsap.to(card, {
        duration: 0.3,
        scale: 0.95,
        ease: 'power2.out'
      });
    });

    card.addEventListener('touchend', () => {
      gsap.to(card, {
        duration: 0.3,
        scale: 1,
        ease: 'power2.out'
      });
    });
  });

  // 禁用长按菜单（可选）
  document.addEventListener('contextmenu', (e) => {
    // 允许在链接上长按
    if (!e.target.closest('a')) {
      e.preventDefault();
    }
  });
}

/**
 * 性能监控（用于调试和优化）
 */
function initPerformanceMonitoring() {
  if (typeof window.performance === 'undefined') return;

  // 页面加载性能
  window.addEventListener('load', () => {
    const perfData = window.performance.timing;
    const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;

    console.log(`📊 页面加载时间: ${pageLoadTime}ms`);

    // 首屏时间
    const firstContentfulPaint = performance.getEntriesByName('first-contentful-paint')[0];
    if (firstContentfulPaint) {
      console.log(`⚡ 首屏时间 (FCP): ${Math.round(firstContentfulPaint.startTime)}ms`);
    }

    // 关键渲染路径优化建议
    if (pageLoadTime > 3000) {
      console.warn('⚠️ 页面加载较慢，建议优化资源');
    }
  });

  // 帧率监控（用于检测性能问题）
  if (window.requestAnimationFrame) {
    let lastTime = performance.now();
    let frameCount = 0;
    let fps = 60;

    function measureFPS() {
      const currentTime = performance.now();
      const deltaTime = currentTime - lastTime;

      frameCount++;

      if (deltaTime >= 1000) {
        fps = frameCount;
        frameCount = 0;
        lastTime = currentTime;

        // 如果 FPS 低于 30，发出警告
        if (fps < 30 && window.location.hash !== '#performance-debug') {
          console.warn(`⚠️ 帧率较低 (${fps} FPS)，可能存在性能瓶颈`);
        }
      }

      requestAnimationFrame(measureFPS);
    }

    // 可选：启用 FPS 监控
    // requestAnimationFrame(measureFPS);
  }
}

/**
 * 懒加载图片（如果有的话）
 */
export function initLazyLoading() {
  if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const img = entry.target;
          img.src = img.dataset.src;
          img.classList.add('loaded');
          observer.unobserve(img);
        }
      });
    });

    document.querySelectorAll('img[data-src]').forEach((img) => {
      imageObserver.observe(img);
    });
  }
}

/**
 * 初始化辅助功能（Accessibility）
 */
export function initAccessibility() {
  // 添加 focus-visible 样式
  const style = document.createElement('style');
  style.textContent = `
    :focus-visible {
      outline: 2px solid #667eea;
      outline-offset: 2px;
    }

    .btn:focus-visible,
    nav a:focus-visible {
      outline: 2px solid #667eea;
      outline-offset: 4px;
    }
  `;
  document.head.appendChild(style);

  // 键盘导航优化
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Home') {
      e.preventDefault();
      if (lenisInstance) {
        lenisInstance.scrollTo(0, { duration: 1.2 });
      } else {
        gsap.to(window, { duration: 1, scrollTo: 0, ease: 'power2.inOut' });
      }
    } else if (e.key === 'End') {
      e.preventDefault();
      if (lenisInstance) {
        lenisInstance.scrollTo(document.body.scrollHeight, { duration: 1.2 });
      } else {
        gsap.to(window, { duration: 1, scrollTo: document.body.scrollHeight, ease: 'power2.inOut' });
      }
    }
  });
}

/**
 * 暗黑模式支持（可选）
 */
export function initDarkModeToggle() {
  // 检测系统暗黑模式偏好
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');

  function updateTheme(isDark) {
    if (isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }

  // 初始化主题
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme) {
    updateTheme(savedTheme === 'dark');
  } else {
    updateTheme(prefersDark.matches);
  }

  // 监听系统主题变化
  prefersDark.addEventListener('change', (e) => {
    updateTheme(e.matches);
  });
}

/**
 * 导出设备信息（用于调试）
 */
export function getDeviceInfo() {
  return {
    isMobile: isMobileDevice,
    isTablet,
    width: window.innerWidth,
    height: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio,
    userAgent: navigator.userAgent
  };
}
