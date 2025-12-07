import React, { useEffect, useRef } from 'react'

export default function DustEffect() {
    const canvasRef = useRef(null)

    useEffect(() => {
        const canvas = canvasRef.current
        const ctx = canvas.getContext('2d')
        let w, h
        let particles = []

        const resize = () => {
            w = canvas.width = window.innerWidth
            h = canvas.height = window.innerHeight
        }

        const createParticle = () => ({
            x: Math.random() * w,
            y: Math.random() * h,
            vx: (Math.random() - 0.5) * 0.5,
            vy: (Math.random() - 0.5) * 0.5,
            size: Math.random() * 2,
            opacity: Math.random() * 0.5
        })

        const init = () => {
            resize()
            for (let i = 0; i < 150; i++) {
                particles.push(createParticle())
            }
        }

        const animate = () => {
            ctx.clearRect(0, 0, w, h)
            particles.forEach(p => {
                p.x += p.vx
                p.y += p.vy
                if (p.x < 0) p.x = w
                if (p.x > w) p.x = 0
                if (p.y < 0) p.y = h
                if (p.y > h) p.y = 0
                ctx.fillStyle = `rgba(255, 255, 255, ${p.opacity})`
                ctx.fillRect(p.x, p.y, p.size, p.size)
            })
            requestAnimationFrame(animate)
        }

        init()
        window.addEventListener('resize', resize)
        animate()

        return () => window.removeEventListener('resize', resize)
    }, [])

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
                zIndex: 0
            }}
        />
    )
}
