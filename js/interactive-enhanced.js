// 鼠标跟踪与3D交互增强

export function initMouseFollower() {
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
    let isMouseDown = false;

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
    const cards = document.querySelectorAll('.card, .project-card');

    cards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const rotateY = ((x / rect.width) - 0.5) * 15;
            const rotateX = -((y / rect.height) - 0.5) * 15;

            card.style.transform = `
                perspective(1200px)
                rotateX(${rotateX}deg)
                rotateY(${rotateY}deg)
                translateZ(20px)
            `;
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = 'rotateX(0) rotateY(0) translateZ(0)';
        });
    });
}

export function initSkillBarAnimation() {
    const skillBars = document.querySelectorAll('.skill-item');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const barFill = entry.target.querySelector('.bar-fill');
                if (barFill && !barFill.classList.contains('animated')) {
                    const targetWidth = barFill.getAttribute('data-width') || '100%';
                    barFill.style.setProperty('--target-width', targetWidth);
                    barFill.style.width = targetWidth;
                    barFill.classList.add('animated');
                    observer.unobserve(entry.target);
                }
            }
        });
    }, { threshold: 0.3 });

    skillBars.forEach(bar => observer.observe(bar));
}

export function initGlowEffect() {
    const cards = document.querySelectorAll('.card, .project-card');

    cards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.animation = 'glowPulse 2s ease-in-out infinite';
        });

        card.addEventListener('mouseleave', () => {
            card.style.animation = 'none';
        });
    });
}

export function initScrollReveal() {
    const elements = document.querySelectorAll('.card, .project-card, h2');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animation = 'titleSlideIn 0.8s ease-out forwards';
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });

    elements.forEach(el => observer.observe(el));
}

export function initParallaxScroll() {
    const section1 = document.querySelector('.section-1-content');

    window.addEventListener('scroll', () => {
        const scrollY = window.scrollY;
        if (section1 && scrollY < window.innerHeight) {
            section1.style.transform = `translateY(${scrollY * 0.3}px)`;
        }
    });
}
