// 鼠标跟踪与3D交互增强

let isMobile = window.innerWidth < 768;

export function initMouseFollower() {
    // 移动设备不需要鼠标跟随
    if (isMobile) return;

    const follower = document.createElement('div');
    follower.style.cssText = `
        position: fixed;
        width: 40px;
        height: 40px;
        background: radial-gradient(circle, rgba(0, 102, 204, 0.6) 0%, rgba(0, 102, 204, 0.2) 70%);
        border-radius: 50%;
        pointer-events: none;
        z-index: 10000;
        box-shadow: 0 0 20px rgba(0, 102, 204, 0.5), inset 0 0 10px rgba(0, 102, 204, 0.3);
        display: none;
        will-change: transform;
    `;

    document.body.appendChild(follower);

    let mouseX = 0, mouseY = 0;
    let followerX = 0, followerY = 0;

    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;
        follower.style.display = 'block';
    });

    document.addEventListener('mouseleave', () => {
        follower.style.display = 'none';
    });

    function updateFollower() {
        followerX += (mouseX - followerX) * 0.3;
        followerY += (mouseY - followerY) * 0.3;
        follower.style.transform = `translate(${followerX - 20}px, ${followerY - 20}px)`;
        requestAnimationFrame(updateFollower);
    }

    updateFollower();
}

export function init3DCardTilt() {
    if (isMobile) return;

    const cards = document.querySelectorAll('.card, .project-card');

    cards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const rotateY = ((x / rect.width) - 0.5) * 12;
            const rotateX = -((y / rect.height) - 0.5) * 12;

            card.style.transform = `
                perspective(1200px)
                rotateX(${rotateX}deg)
                rotateY(${rotateY}deg)
                translateZ(15px)
            `;
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = 'perspective(1200px) rotateX(0) rotateY(0) translateZ(0)';
        });
    });
}

export function initSkillBarAnimation() {
    const skillBars = document.querySelectorAll('.bar-fill');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !entry.target.classList.contains('animated')) {
                const targetWidth = entry.target.getAttribute('data-width') || '100%';
                entry.target.style.animation = `progressFill 1.2s ease-out forwards`;
                entry.target.style.width = targetWidth;
                entry.target.classList.add('animated');
            }
        });
    }, { threshold: 0.3 });

    skillBars.forEach(bar => observer.observe(bar));
}

export function initGlowEffect() {
    if (isMobile) return;

    const cards = document.querySelectorAll('.card, .project-card');

    cards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            if (card.style.animation && card.style.animation !== 'none') {
                card.style.animation = 'glowPulse 2s ease-in-out infinite';
            }
        });

        card.addEventListener('mouseleave', () => {
            card.style.animation = 'none';
        });
    });
}

export function initScrollReveal() {
    const elements = document.querySelectorAll('.card, .project-card, .greeting-tag, .tech-tags, .quick-facts');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting && !entry.target.classList.contains('revealed')) {
                // 添加延迟动画
                const delay = index * 0.05;
                entry.target.style.animationDelay = `${delay}s`;
                entry.target.classList.add('revealed');
            }
        });
    }, { threshold: 0.1 });

    elements.forEach(el => observer.observe(el));
}

export function initParallaxScroll() {
    const section1Content = document.querySelector('.section-1-content');
    const section1Before = document.querySelector('.section-1::before');
    const section1After = document.querySelector('.section-1::after');

    if (!section1Content) return;

    window.addEventListener('scroll', () => {
        const scrollY = window.scrollY;
        const windowHeight = window.innerHeight;

        // 只在第一屏内应用视差效果
        if (scrollY < windowHeight) {
            if (section1Content) {
                section1Content.style.transform = `translateY(${scrollY * 0.3}px)`;
            }
        }
    }, { passive: true });
}
