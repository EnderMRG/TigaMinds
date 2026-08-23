'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import Link from 'next/link';
import { Leaf, ChevronDown, Zap, ScanLine, TrendingUp, ArrowRight } from 'lucide-react';
import anime from 'animejs';

// ─── Constants ────────────────────────────────────────────────────────────────
const TOTAL_FRAMES = 50;
const SCROLL_PER_FRAME = 180; // px of scroll per frame
const PINNED_SCROLL = TOTAL_FRAMES * SCROLL_PER_FRAME; // ~9000px

const pad = (n: number) => String(n).padStart(3, '0');
const frameSrc = (n: number) => `/landing/frame_${pad(n)}.png`;

// ─── Chapter definitions ──────────────────────────────────────────────────────
interface Chapter {
  startFrame: number;
  endFrame: number;
  eyebrow: string;
  heading: string;
  sub: string;
  align: 'left' | 'center' | 'right';
}

const CHAPTERS: Chapter[] = [
  {
    startFrame: 5,
    endFrame: 10,
    eyebrow: 'Assam, India',
    heading: 'Every leaf\ntells a story.',
    sub: 'The best estates have always known it. Now the data does too.',
    align: 'right',
  },
  {
    startFrame: 12,
    endFrame: 20,
    eyebrow: 'The Problem',
    heading: 'Thousands of signals.\nZero clarity.',
    sub: 'Soil moisture, disease risk, auction prices — all separate. All too late.',
    align: 'left',
  },
  {
    startFrame: 22,
    endFrame: 36,
    eyebrow: 'CHAI-NET Intelligence',
    heading: 'We read the leaf\nbefore you pluck it.',
    sub: 'AI trained on Assam disease data. Real-time IoT. One decisive score.',
    align: 'right',
  },
  {
    startFrame: 38,
    endFrame: 50,
    eyebrow: 'One platform. Every decision.',
    heading: 'Act today.\nHarvest optimally.\nSell at the right moment.',
    sub: 'From sensor to auction — end-to-end intelligence built for Assam.',
    align: 'center',
  },
];

// ─── Feature data ─────────────────────────────────────────────────────────────
const TeaLeafLoader = () => {
  const leafRef = useRef<SVGPathElement>(null);
  const circleRef = useRef<SVGGElement>(null);

  useEffect(() => {
    if (!leafRef.current || !circleRef.current) return;
    
    // Animate the leaf path drawing
    anime({
      targets: leafRef.current,
      strokeDashoffset: [anime.setDashoffset, 0],
      easing: 'easeInOutSine',
      duration: 2000,
      direction: 'alternate',
      loop: true
    });

    // Rotate the radar circle
    anime({
      targets: circleRef.current,
      rotate: '1turn',
      easing: 'linear',
      duration: 8000,
      loop: true
    });

    // Pulse the control dots
    anime({
      targets: '.control-dot',
      scale: [0.5, 1.2],
      opacity: [0.3, 1, 0.3],
      easing: 'easeInOutSine',
      duration: 1500,
      delay: anime.stagger(200),
      loop: true
    });
  }, []);

  return (
    <div className="relative flex items-center justify-center w-64 h-64">
      <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full overflow-visible">
        {/* Geometric crosshairs */}
        <line x1="20" y1="50" x2="80" y2="50" stroke="rgba(34, 197, 94, 0.2)" strokeWidth="0.5" strokeDasharray="2 2" />
        <line x1="50" y1="20" x2="50" y2="80" stroke="rgba(34, 197, 94, 0.2)" strokeWidth="0.5" strokeDasharray="2 2" />
        
        {/* Rotating radar elements */}
        <g ref={circleRef} style={{ transformOrigin: '50px 50px' }}>
          <circle cx="50" cy="50" r="35" fill="none" stroke="rgba(34, 197, 94, 0.3)" strokeWidth="0.5" strokeDasharray="4 6" />
          <circle cx="50" cy="50" r="25" fill="none" stroke="rgba(34, 197, 94, 0.15)" strokeWidth="1" />
          {/* A sweeping radar arc */}
          <path d="M 50 15 A 35 35 0 0 1 85 50" fill="none" stroke="rgba(34, 197, 94, 0.6)" strokeWidth="1" />
        </g>

        {/* Central Detailed Tea Leaf */}
        <g>
          <path 
            ref={leafRef}
            d="M 50 92 L 50 82 C 15 70, 15 35, 50 8 C 85 35, 85 70, 50 82 Q 62 45, 50 16" 
            fill="none" 
            stroke="#22c55e" 
            strokeWidth="1.5" 
            strokeLinecap="round" 
            strokeLinejoin="round" 
          />
        </g>

        {/* Orange control dots from user's reference */}
        <g className="fill-orange-400">
          <circle className="control-dot" cx="50" cy="15" r="1.5" />
          <circle className="control-dot" cx="50" cy="85" r="1.5" />
          <circle className="control-dot" cx="15" cy="50" r="1.5" />
          <circle className="control-dot" cx="85" cy="50" r="1.5" />
          <circle className="control-dot" cx="50" cy="50" r="1" fill="#22c55e" />
        </g>
      </svg>
    </div>
  );
};

const FEATURES = [
  {
    icon: Zap,
    title: 'Real-Time IoT Monitoring',
    body: 'Soil moisture, temperature, humidity, and rainfall tracked continuously. Health scores computed on every reading.',
    stat: '5 sensor types',
  },
  {
    icon: ScanLine,
    title: 'AI Leaf Disease Scanner',
    body: 'Upload a photo from the field. YOLOv5 + CNN detects Red Rust, Blister Blight, and six other diseases in seconds.',
    stat: '8 disease classes',
  },
  {
    icon: TrendingUp,
    title: 'Guwahati Market Intelligence',
    body: 'ML price forecasting calibrated on 12 months of Guwahati auction history. Know when to hold and when to sell.',
    stat: '6 auction markets',
  },
];

// ─── Component ────────────────────────────────────────────────────────────────
export default function HomePage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const frameIndexRef = useRef(0);
  const framesRef = useRef<HTMLImageElement[]>([]);
  const [currentFrame, setCurrentFrame] = useState(1);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [framesLoaded, setFramesLoaded] = useState(false);
  const [showChevron, setShowChevron] = useState(true);
  const [viewportHeight, setViewportHeight] = useState(800);
  const [viewportWidth, setViewportWidth] = useState(1200);
  const rafRef = useRef<number | null>(null);

  // ── Set viewport dimensions client-side only ──────────────────────────────
  useEffect(() => {
    setViewportHeight(window.innerHeight);
    setViewportWidth(window.innerWidth);
    const onResize = () => {
      setViewportHeight(window.innerHeight);
      setViewportWidth(window.innerWidth);
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // ── Preload all frames ──────────────────────────────────────────────────────
  useEffect(() => {
    let loaded = 0;
    const imgs: HTMLImageElement[] = [];
    for (let i = 1; i <= TOTAL_FRAMES; i++) {
      const img = new Image();
      img.src = frameSrc(i);
      img.onload = () => {
        loaded++;
        if (loaded === TOTAL_FRAMES) setFramesLoaded(true);
      };
      img.onerror = () => {
        loaded++;
        if (loaded === TOTAL_FRAMES) setFramesLoaded(true);
      };
      imgs.push(img);
    }
    framesRef.current = imgs;
  }, []);

  // ── Draw frame on canvas ────────────────────────────────────────────────────
  const drawFrame = useCallback((index: number) => {
    const canvas = canvasRef.current;
    const img = framesRef.current[index];
    if (!canvas || !img || !img.complete) return;
    const ctx = canvas.getContext('2d', { alpha: false }); // Optimize for opaque images
    if (!ctx) return;
    // Canvas internal dimensions are in physical pixels (dpr-scaled)
    const { width, height } = canvas;
    ctx.imageSmoothingEnabled = false; // Disable to improve draw performance on large frames
    const scale = Math.max(width / img.naturalWidth, height / img.naturalHeight);
    const sw = img.naturalWidth * scale;
    const sh = img.naturalHeight * scale;
    ctx.clearRect(0, 0, width, height);
    ctx.drawImage(img, (width - sw) / 2, (height - sh) / 2, sw, sh);
  }, []);

  // ── Resize canvas — DPR-aware ───────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const cssW = window.innerWidth;
      const cssH = window.innerHeight;
      // Physical pixel dimensions for crisp rendering on HiDPI screens
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
      // Keep CSS size the same so the element fills the viewport
      canvas.style.width = cssW + 'px';
      canvas.style.height = cssH + 'px';
      drawFrame(frameIndexRef.current);
    };
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, [drawFrame]);

  // ── Scroll handler ──────────────────────────────────────────────────────────
  useEffect(() => {
    const onScroll = () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        const container = containerRef.current;
        if (!container) return;
        const scrollY = window.scrollY;
        const progress = Math.min(scrollY / PINNED_SCROLL, 1);
        const frameIdx = Math.min(Math.round(progress * (TOTAL_FRAMES - 1)), TOTAL_FRAMES - 1);
        const frameNum = frameIdx + 1;

        setScrollProgress(progress);
        setCurrentFrame(frameNum);
        if (scrollY > viewportHeight * 0.1) setShowChevron(false);
        else setShowChevron(true);

        if (frameIdx !== frameIndexRef.current) {
          frameIndexRef.current = frameIdx;
          drawFrame(frameIdx);
        }
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [drawFrame]);

  // ── Draw first frame once loaded ────────────────────────────────────────────
  useEffect(() => {
    if (framesLoaded) drawFrame(0);
  }, [framesLoaded, drawFrame]);

  // ── Compute active chapter overlay ─────────────────────────────────────────
  const activeChapter = CHAPTERS.find(
    (c) => currentFrame >= c.startFrame && currentFrame <= c.endFrame
  );

  const chapterOpacity = (() => {
    if (!activeChapter) return 0;
    const { startFrame, endFrame } = activeChapter;
    const span = endFrame - startFrame;
    const pos = currentFrame - startFrame;
    const fadeFrames = Math.min(3, Math.floor(span * 0.25));
    
    if (pos < fadeFrames) return pos / fadeFrames;
    if (endFrame !== TOTAL_FRAMES && pos > span - fadeFrames) return (span - pos) / fadeFrames;
    return 1;
  })();

  const alignClass =
    activeChapter?.align === 'left'
      ? 'items-start text-left pl-12 md:pl-24'
      : activeChapter?.align === 'right'
      ? 'items-end text-right pr-12 md:pr-24'
      : 'items-center text-center';

  const heroProgress = Math.min(scrollProgress / 0.08, 1);

  // ── Roaming Logo Math ──
  const isMd = viewportWidth >= 768;
  const navbarX = isMd ? 40 : 24; // px-10 is 40px, px-6 is 24px
  const navbarY = 16; // py-4 is 16px
  
  const heroX = viewportWidth * 0.06;
  const heroY = viewportHeight * 0.22;
  
  const currentX = navbarX + (heroX - navbarX) * (1 - heroProgress);
  const currentY = navbarY + (heroY - navbarY) * (1 - heroProgress);
  
  const heroFontSize = isMd ? viewportWidth * 0.13 : viewportWidth * 0.16;
  const currentScale = 1 + ((heroFontSize / 18) - 1) * (1 - heroProgress);

  return (
    <div className="bg-[#0a0f0a] text-white">
      {/* ── Loading Overlay ── */}
      <div 
        className={`fixed inset-0 z-[100] flex flex-col items-center justify-center bg-[#0a0f0a] transition-opacity duration-1000 ${
          framesLoaded ? 'opacity-0 pointer-events-none' : 'opacity-100 pointer-events-auto'
        }`}
      >
        <TeaLeafLoader />
        <div className="mt-2 text-xs font-bold tracking-[0.4em] text-white/50 uppercase">
          Initializing CHAI-NET
        </div>
      </div>

      {/* ── Navbar ── */}
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-4 md:px-10">
        <div className="w-[120px]" /> {/* Spacer for roaming logo */}
        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="text-sm text-white/60 hover:text-white transition-colors px-3 py-1.5 rounded-md hover:bg-white/5"
          >
            Sign In
          </Link>
          <Link
            href="/login"
            className="text-sm font-medium bg-[#22c55e] text-white px-4 py-1.5 rounded-full hover:bg-[#16a34a] transition-colors shadow-lg shadow-green-900/30"
          >
            Try Demo
          </Link>
        </div>
      </nav>

      {/* ── Roaming Logo ── */}
      <Link 
        href="/" 
        className="fixed z-50 flex items-center group"
        style={{ 
          left: `${currentX}px`, 
          top: `${currentY}px`,
        }}
      >
        <div 
          className="rounded-lg bg-[#22c55e] flex items-center justify-center shadow-lg shadow-green-900/40" 
          style={{ 
            opacity: Math.pow(heroProgress, 2), 
            width: `${heroProgress * 32}px`, 
            height: `${heroProgress * 32}px`,
            marginRight: `${heroProgress * 8}px`,
            overflow: 'hidden'
          }}
        >
          <Leaf className="h-4 w-4 text-white flex-shrink-0" />
        </div>

        <div className="relative origin-top-left" style={{ transform: `scale(${currentScale})` }}>
          <div 
            className="absolute left-0 bottom-[105%] whitespace-nowrap flex items-center gap-1 pointer-events-none"
            style={{ opacity: 1 - Math.pow(heroProgress, 1.2) }}
          >
            <div className="h-[1.5px] w-[1.5px] rounded-full bg-[#fbf9f6]" />
            <span className="text-[2.5px] font-bold tracking-[0.2em] uppercase text-white drop-shadow-md">
              Intelligent Tea Garden Management
            </span>
          </div>
          <span 
            className="font-black tracking-[-0.03em] text-[#fbf9f6] block leading-[0.75]"
            style={{ 
              fontSize: '18px',
              textShadow: heroProgress < 0.5 ? '0 4px 16px rgba(0,0,0,0.6)' : 'none',
            }}
          >
            CHAI-NET
          </span>
        </div>
      </Link>

      {/* ── Scroll progress bar ── */}
      <div className="fixed left-0 top-0 bottom-0 w-[3px] z-40 bg-white/5">
        <div
          className="w-full bg-[#22c55e] transition-none origin-top"
          style={{ height: `${scrollProgress * 100}%` }}
        />
      </div>

      {/* ── Pinned canvas sequence ── */}
      <div
        ref={containerRef}
        style={{ height: `${PINNED_SCROLL + viewportHeight}px` }}
      >
        <div className="sticky top-0 h-screen w-full overflow-hidden">
          {/* Canvas */}
          <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full"
            style={{ filter: 'brightness(0.82)' }}
          />

          {/* Vignette */}
          <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-transparent to-black/60 pointer-events-none" />
          <div className="absolute inset-0 bg-gradient-to-r from-black/30 via-transparent to-black/30 pointer-events-none" />

          {/* Massive Hero Overlay (ORYZO style boxes) */}
          <div 
            className="absolute inset-0 z-30 pointer-events-none flex flex-col justify-end p-8 md:p-16"
            style={{ 
              opacity: 1 - Math.pow(heroProgress, 1.5),
              transform: `scale(${1 - heroProgress * 0.4}) translate(-${heroProgress * 5}vw, -${heroProgress * 10}vh)`,
              transformOrigin: 'bottom left'
            }}
          >
            {/* Bottom section */}
            <div className="flex justify-end items-end w-full mb-16 md:mb-4 gap-8">
              {/* Text block on bottom right */}
              <div className="w-full max-w-xs md:max-w-md text-right">
                <p className="text-lg md:text-2xl text-white/90 font-medium leading-tight drop-shadow-lg">
                  Designed to monitor, predict, and optimize in all the right ways. 
                  CHAI-NET makes the simplest moment feel considered.
                </p>
              </div>
            </div>
          </div>

          {/* Chapter overlay */}
          <div
            className={`absolute inset-0 flex flex-col justify-center gap-4 px-6 pointer-events-none transition-none ${alignClass}`}
            style={{ opacity: chapterOpacity }}
          >
            {activeChapter && (
              <>
                <span className="text-[11px] font-semibold tracking-[0.2em] uppercase text-[#86efac]">
                  {activeChapter.eyebrow}
                </span>
                <h2
                  className="text-4xl md:text-6xl lg:text-7xl font-bold leading-[1.05] tracking-[-0.03em] text-white"
                  style={{ textShadow: '0 2px 32px rgba(0,0,0,0.6)', whiteSpace: 'pre-line' }}
                >
                  {activeChapter.heading}
                </h2>
                <p
                  className="text-base md:text-lg text-white/75 max-w-sm mb-4"
                  style={{ textShadow: '0 1px 16px rgba(0,0,0,0.8)' }}
                >
                  {activeChapter.sub}
                </p>
                {/* Go to Dashboard button on the final chapter */}
                {activeChapter.endFrame === TOTAL_FRAMES && (
                  <div 
                    className="mt-6 transition-all duration-1000 delay-300"
                    style={{ 
                      opacity: currentFrame >= activeChapter.startFrame + 2 ? 1 : 0, 
                      transform: currentFrame >= activeChapter.startFrame + 2 ? 'translateY(0)' : 'translateY(20px)',
                      pointerEvents: currentFrame >= activeChapter.startFrame + 2 ? 'auto' : 'none'
                    }}
                  >
                    <Link
                      href="/login"
                      className="inline-flex items-center gap-2 bg-[#22c55e] text-white text-sm font-bold tracking-wide px-8 py-4 rounded-full hover:bg-[#16a34a] transition-all duration-300 shadow-2xl shadow-green-900/50 hover:shadow-green-900/80 hover:scale-[1.05]"
                    >
                      Go to Dashboard
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Chevron scroll hint */}
          <div
            className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1 transition-opacity duration-500"
            style={{ opacity: showChevron ? 1 : 0 }}
          >
            <span className="text-[10px] tracking-widest uppercase text-white/40">Scroll</span>
            <ChevronDown className="h-5 w-5 text-white/40 animate-bounce" />
          </div>

          {/* Frame counter — subtle */}
          <div className="absolute bottom-8 right-8 text-[10px] tabular-nums text-white/20 font-mono">
            {String(currentFrame).padStart(2, '0')} / {TOTAL_FRAMES}
          </div>
        </div>
      </div>
    </div>
  );
}
