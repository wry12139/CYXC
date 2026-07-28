/**
 * GSAP 动画系统
 * 管理所有交互动画、滚动动画和复杂序列
 */

let masterTimeline;
let scrollTriggers = [];
let isInitialized = false;

export function initGsapAnimations() {
  if (isInitialized) return;

  // 注册 ScrollTrigger 插件
  gsap.registerPlugin(ScrollTrigger);

  // 创建主时间轴
  masterTimeline = gsap.timeline();

  // 初始化各类动画
  initPageLoadAnimation();
  initCardHoverAnimations();
  initScrollTriggerAnimations();
  initNavbarAnimations();
  initParallaxEffects();

  isInitialized = true;
}

/**
 * 页面加载动画序列
 */
function initPageLoadAnimation() {
  const tl = gsap.timeline();

  // 导航栏淡入并向下滑动
  tl.to('nav', {
    duration: 0.6,
    opacity: 1,
    y: 0,
    ease: 'back.out(1.7)'
  }, 0)

  // 名字框进场
  .to('.name-graphic', {
    duration: 0.8,
    opacity: 1,
    scale: 1,
    ease: 'back.out(1.5)'
  }, 0.2)

  // 信息框逐行出现
  .to('.role', {
    duration: 0.6,
    opacity: 1,
    x: 0,
    ease: 'power2.out'
  }, 0.4)

  .to('.intro', {
    duration: 0.6,
    opacity: 1,
    x: 0,
    ease: 'power2.out'
  }, 0.6)

  // 按钮组依次进场
  .to('.btn-group', {
    duration: 0.6,
    opacity: 1,
    y: 0,
    ease: 'power2.out'
  }, 0.8);

  // 返回顶部按钮淡入
  gsap.to('button:contains("顶部")', {
    duration: 0.4,
    opacity: 1,
    delay: 1.5
  });
}

/**
 * 卡片悬停动画
 */
function initCardHoverAnimations() {
  document.querySelectorAll('.card, .project-card').forEach((card) => {
    const tl = gsap.timeline({ paused: true });

    // 悬停进入：3D 倾斜 + 浮起 + 阴影增强
    tl.to(
      card,
      {
        duration: 0.4,
        y: -15,
        boxShadow: '0 30px 60px rgba(102, 126, 234, 0.35)',
        ease: 'power2.out',
        overwrite: 'auto'
      },
      0
    )
    .to(
      card,
      {
        duration: 0.4,
        transform: 'perspective(1000px) rotateX(5deg) rotateY(-5deg) scale(1.02)',
        ease: 'power2.out'
      },
      0
    );

    // 鼠标进入
    card.addEventListener('mouseenter', () => tl.play());

    // 鼠标离开
    card.addEventListener('mouseleave', () => tl.reverse());
  });

  // 按钮悬停
  document.querySelectorAll('.btn').forEach((btn) => {
    const tl = gsap.timeline({ paused: true });

    tl.to(btn, {
      duration: 0.3,
      scale: 1.1,
      y: -5,
      ease: 'back.out(1.3)',
      boxShadow: '0 20px 50px rgba(102, 126, 234, 0.4)'
    });

    btn.addEventListener('mouseenter', () => tl.play());
    btn.addEventListener('mouseleave', () => tl.reverse());
  });
}

/**
 * ScrollTrigger 滚动触发动画
 */
function initScrollTriggerAnimations() {
  // Section 2 卡片进场
  gsap.utils.toArray('.card').forEach((card, index) => {
    gsap.to(card, {
      scrollTrigger: {
        trigger: card,
        start: 'top 80%',
        end: 'top 50%',
        scrub: false,
        markers: false
      },
      duration: 0.8,
      opacity: 1,
      y: 0,
      rotation: 0,
      ease: 'power2.out',
      delay: index * 0.1
    });
  });

  // Section 3 项目卡片错行进场
  gsap.utils.toArray('.project-card').forEach((card, index) => {
    const xStart = index % 2 === 0 ? -100 : 100;

    gsap.to(card, {
      scrollTrigger: {
        trigger: card,
        start: 'top 85%',
        end: 'top 55%',
        scrub: 1,
        markers: false
      },
      duration: 0.8,
      opacity: 1,
      x: 0,
      rotation: 0,
      ease: 'power2.out'
    });

    card.style.opacity = '0';
    card.style.transform = `translateX(${xStart}px)`;
  });

  // 标题动画
  gsap.utils.toArray('h2').forEach((title) => {
    gsap.to(title, {
      scrollTrigger: {
        trigger: title,
        start: 'top 80%',
        markers: false
      },
      duration: 0.8,
      opacity: 1,
      y: 0,
      ease: 'power2.out'
    });

    title.style.opacity = '0';
    title.style.transform = 'translateY(20px)';
  });
}

/**
 * 导航栏动态效果
 */
function initNavbarAnimations() {
  const navbar = document.querySelector('nav');
  let lastScrollY = 0;

  ScrollTrigger.create({
    onUpdate: (self) => {
      const scrollY = self.getVelocity();

      // 根据滚动位置改变导航栏样式
      if (window.scrollY > 100) {
        gsap.to(navbar, {
          duration: 0.3,
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          boxShadow: '0 4px 20px rgba(102, 126, 234, 0.2)',
          backdropFilter: 'blur(15px)',
          overwrite: 'auto'
        });

        gsap.to('nav a', {
          duration: 0.3,
          color: '#667eea'
        });
      } else {
        gsap.to(navbar, {
          duration: 0.3,
          backgroundColor: 'rgba(255, 255, 255, 0.8)',
          boxShadow: '0 2px 10px rgba(102, 126, 234, 0.15)',
          overwrite: 'auto'
        });

        gsap.to('nav a', {
          duration: 0.3,
          color: '#667eea'
        });
      }
    }
  });

  // 导航链接点击动画
  document.querySelectorAll('nav a').forEach((link) => {
    link.addEventListener('click', function (e) {
      e.preventDefault();

      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        gsap.to(window, {
          duration: 1.2,
          scrollTo: target,
          ease: 'power2.inOut'
        });
      }
    });
  });

  // 导航链接 underline 动画
  document.querySelectorAll('nav a').forEach((link) => {
    const underline = document.createElement('div');
    underline.style.cssText = `
      position: absolute;
      bottom: -5px;
      left: 0;
      width: 0;
      height: 2px;
      background: linear-gradient(90deg, #667eea, #764ba2);
      border-radius: 1px;
    `;
    link.style.position = 'relative';
    link.appendChild(underline);

    link.addEventListener('mouseenter', () => {
      gsap.to(underline, {
        duration: 0.3,
        width: '100%',
        ease: 'power2.out'
      });
    });

    link.addEventListener('mouseleave', () => {
      gsap.to(underline, {
        duration: 0.3,
        width: 0,
        ease: 'power2.out'
      });
    });
  });
}

/**
 * 视差滚动效果
 */
function initParallaxEffects() {
  // Section 1 背景视差
  gsap.to('.section-1::before', {
    scrollTrigger: {
      trigger: '.section-1',
      start: 'top top',
      end: 'bottom top',
      scrub: 1,
      markers: false
    },
    y: 100,
    ease: 'none'
  });

  gsap.to('.section-1::after', {
    scrollTrigger: {
      trigger: '.section-1',
      start: 'top top',
      end: 'bottom top',
      scrub: 1,
      markers: false
    },
    y: -80,
    ease: 'none'
  });

  // Section 1 内容视差
  gsap.to('.section-1-content', {
    scrollTrigger: {
      trigger: '.section-1',
      start: 'top top',
      end: 'bottom top',
      scrub: 1,
      markers: false
    },
    y: -50,
    opacity: 0.7,
    ease: 'none'
  });

  // Section 2 标题视差
  gsap.to('.section-2 h2', {
    scrollTrigger: {
      trigger: '.section-2',
      start: 'top center',
      end: 'center center',
      scrub: 1,
      markers: false
    },
    y: -30,
    ease: 'none'
  });

  // Section 3 背景视差
  gsap.to('.section-3::before', {
    scrollTrigger: {
      trigger: '.section-3',
      start: 'top top',
      end: 'bottom top',
      scrub: 1,
      markers: false
    },
    y: 120,
    ease: 'none'
  });

  gsap.to('.section-3::after', {
    scrollTrigger: {
      trigger: '.section-3',
      start: 'top top',
      end: 'bottom top',
      scrub: 1,
      markers: false
    },
    y: -100,
    ease: 'none'
  });
}

/**
 * 初始化元素状态
 */
export function prepareElementsForAnimation() {
  // 初始隐藏需要动画的元素
  gsap.set('nav', { opacity: 0, y: -20 });
  gsap.set('.name-graphic', { opacity: 0, scale: 0.8 });
  gsap.set('.role, .intro, .btn-group', { opacity: 0, x: -30 });
  gsap.set('.card, .project-card', { opacity: 0, y: 30 });
  gsap.set('h2', { opacity: 0, y: 20 });
}

/**
 * 清理动画资源
 */
export function cleanupGsapAnimations() {
  // 清理所有 ScrollTrigger
  ScrollTrigger.getAll().forEach((trigger) => trigger.kill());

  // 清理所有 GSAP 动画
  gsap.killTweensOf('*');
}

/**
 * 外部接口：触发卡片选中动画
 */
export function animateCardSelection(card) {
  gsap.to(card, {
    duration: 0.4,
    scale: 1.05,
    boxShadow: '0 30px 80px rgba(102, 126, 234, 0.5)',
    ease: 'back.out(1.5)'
  });
}

/**
 * 外部接口：触发返回顶部动画
 */
export function animateScrollToTop() {
  gsap.to(window, {
    duration: 1.5,
    scrollTo: 0,
    ease: 'power2.inOut'
  });
}
