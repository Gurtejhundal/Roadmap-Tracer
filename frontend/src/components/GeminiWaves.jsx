import { useEffect, useRef } from 'react';

export default function GeminiWaves() {
    const canvasRef = useRef(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        let width, height;
        let animationFrameId;
        let time = 0;

        const resize = () => {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
        };

        // Configuration for the waves
        const lines = [
            { color: 'rgba(59, 130, 246, 0.5)', speed: 0.002, amplitude: 100, yOffset: 0 }, // Blue
            { color: 'rgba(236, 72, 153, 0.5)', speed: 0.003, amplitude: 150, yOffset: 50 }, // Pink
            { color: 'rgba(147, 51, 234, 0.4)', speed: 0.0015, amplitude: 120, yOffset: -50 }, // Purple
            { color: 'rgba(6, 182, 212, 0.3)', speed: 0.004, amplitude: 80, yOffset: 20 }, // Cyan
        ];

        const animate = () => {
            ctx.clearRect(0, 0, width, height); // Clear canvas
            /* 
               Create a dark gradient background if needed, 
               but we handle background color in CSS usually. 
               We'll just draw waves here over transparency.
            */

            lines.forEach((line, index) => {
                ctx.beginPath();
                ctx.strokeStyle = line.color;
                ctx.lineWidth = 2;

                // Draw wave
                for (let x = 0; x <= width; x += 10) {
                    // Complex wave formula: combines multiple sine waves for organic feel
                    const y = height / 2 + line.yOffset +
                        Math.sin(x * 0.003 + time * line.speed + index) * line.amplitude * Math.sin(time * 0.001);

                    if (x === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                }

                ctx.stroke();

                // Optional: Add a subtle glow/fill below the wave for volume
                // ctx.lineTo(width, height);
                // ctx.lineTo(0, height);
                // ctx.fillStyle = line.color.replace('0.5', '0.05');
                // ctx.fill();
            });

            // Add some floating sparkles for that "magic" feel
            const sparkleCount = 4;
            for (let i = 0; i < sparkleCount; i++) {
                const x = (Math.sin(time * 0.0005 + i) * 0.5 + 0.5) * width;
                const y = (Math.cos(time * 0.001 + i) * 0.5 + 0.5) * height;

                const grad = ctx.createRadialGradient(x, y, 0, x, y, 4);
                grad.addColorStop(0, 'white');
                grad.addColorStop(1, 'transparent');

                ctx.fillStyle = grad;
                ctx.beginPath();
                ctx.arc(x, y, 4, 0, Math.PI * 2);
                ctx.fill();
            }

            time += 1;
            animationFrameId = requestAnimationFrame(animate);
        };

        window.addEventListener('resize', resize);
        resize();
        animate();

        return () => {
            window.removeEventListener('resize', resize);
            cancelAnimationFrame(animationFrameId);
        };
    }, []);

    return (
        <canvas
            ref={canvasRef}
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                pointerEvents: 'none',
                zIndex: 0,
                filter: 'blur(30px) brightness(1.5)', // High blur for that ethereal voice assistant look
                opacity: 0.8
            }}
        />
    );
}
