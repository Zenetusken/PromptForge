<script lang="ts">
	import { onMount } from "svelte";
	import { optimizationState } from "$lib/stores/optimization.svelte";

	let { wallpaper = false }: { wallpaper?: boolean } = $props();

	let svgEl: SVGSVGElement | undefined = $state();

	onMount(() => {
		if (!svgEl) return;
		const observer = new IntersectionObserver(
			([entry]) => {
				if (entry.isIntersecting) svgEl?.unpauseAnimations();
				else svgEl?.pauseAnimations();
			},
			{ threshold: 0 },
		);
		observer.observe(svgEl);
		return () => observer.disconnect();
	});

	type LogoMode = "idle" | "forging" | "complete";

	let mode: LogoMode = $derived.by(() => {
		if (optimizationState.result) return "complete";
		if (optimizationState.isRunning) return "forging";
		return "idle";
	});

	let stepsComplete = $derived.by(() => {
		if (!optimizationState.currentRun) return 0;
		return optimizationState.currentRun.steps.filter(
			(s) => s.status === "complete",
		).length;
	});

	// --- Reactive animation parameters ---
	let cyanBlur = $derived(
		mode === "forging"
			? 5 + stepsComplete * 2
			: mode === "complete"
				? 14
				: 5,
	);
	let beamBlur = $derived(
		mode === "forging" ? 6 + stepsComplete : mode === "complete" ? 10 : 5,
	);

	let coreDur = $derived(
		mode === "forging"
			? `${Math.max(3, 15 - stepsComplete * 3)}s`
			: mode === "complete"
				? "15s"
				: "24s",
	);
	// Tendrils spin much slower than the turbine — majestic drift
	let tendrilSpinDur = $derived(
		mode === "forging" ? "40s" : mode === "complete" ? "50s" : "60s",
	);
	let titleClass = $derived(mode === "complete" ? "bl-text-shimmer" : "");

	// ── Constants ────────────────────────────────────────────────────
	const INNER_R = 30;
	const MID_R = 52;
	const OUTER_R = 80;
	const CX = 500;
	const CY = 320;
	const PI2 = Math.PI * 2;
	const f = (n: number) => n.toFixed(1);

	// ── 3D Cylinder Constants ────────────────────────────────────────
	const CYL_DEPTH = 60;
	const CYL_ANGLE = Math.PI * 0.75; // 135 degrees (bottom-left)
	const CYL_DX = Math.cos(CYL_ANGLE) * CYL_DEPTH;
	const CYL_DY = Math.sin(CYL_ANGLE) * CYL_DEPTH;
	const CYL_STEPS = 24;

	// ── Latitudinal Cylinder Arcs ──
	const latArcs = [0.2, 0.5, 0.8].map((pct) => {
		const cx = CYL_DX * pct;
		const cy = CYL_DY * pct;
		const r = OUTER_R;
		const startX = cx + r * Math.cos(CYL_ANGLE - Math.PI / 2);
		const startY = cy + r * Math.sin(CYL_ANGLE - Math.PI / 2);
		const endX = cx + r * Math.cos(CYL_ANGLE + Math.PI / 2);
		const endY = cy + r * Math.sin(CYL_ANGLE + Math.PI / 2);
		return `M ${f(startX)},${f(startY)} A ${r} ${r} 0 0 1 ${f(endX)},${f(endY)}`;
	});
	// ── Turbine blades: Solid, overlapping jet engine fan blades ────
	const BLADE_COUNT = 24;
	const INNER_BLADE_COUNT = 18;
	const MICRO_BLADE_COUNT = 12;
	const BLADE_SWEEP = (16 * Math.PI) / 180;
	const INNER_BLADE_SWEEP = (-12 * Math.PI) / 180; // Counter-rotating inner blades
	const MICRO_BLADE_SWEEP = (10 * Math.PI) / 180;

	function generateBlades(
		count: number,
		angularOffset: number,
		widthScale: number,
		layer: "outer" | "inner" | "micro" = "outer",
	) {
		const slotHalfW = (PI2 / count) * 0.75 * widthScale;

		let startR = MID_R + 2;
		let endR = OUTER_R;
		let sweep = BLADE_SWEEP;

		if (layer === "inner") {
			startR = INNER_R;
			endR = MID_R - 2;
			sweep = INNER_BLADE_SWEEP;
		} else if (layer === "micro") {
			startR = 6;
			endR = INNER_R - 4;
			sweep = MICRO_BLADE_SWEEP;
		}
		return Array.from({ length: count }, (_, i) => {
			const θ = (i / count) * PI2 + angularOffset;
			const SAMPLES = 16;
			const leading: string[] = [];
			const trailing: string[] = [];

			for (let s = 0; s <= SAMPLES; s++) {
				const t = s / SAMPLES; // 0 = hub, 1 = rim
				const r = startR + (endR - startR) * t;
				const baseAngle = θ + sweep * Math.pow(t, 0.85);

				// Reversed taper: point at hub (t=0) → wide at rim (t=1)
				const halfW = slotHalfW * Math.pow(t, 0.75);

				leading.push(
					`${f(r * Math.cos(baseAngle + halfW))},${f(r * Math.sin(baseAngle + halfW))}`,
				);
				trailing.unshift(
					`${f(r * Math.cos(baseAngle - halfW))},${f(r * Math.sin(baseAngle - halfW))}`,
				);
			}

			return `M${leading.join(" L")} L${trailing.join(" L")} Z`;
		});
	}

	const blades = generateBlades(BLADE_COUNT, 0, 1.0, "outer");
	const innerBlades = generateBlades(INNER_BLADE_COUNT, 0, 1.0, "inner");
	const microBlades = generateBlades(MICRO_BLADE_COUNT, 0, 0.9, "micro");

	// ── Shadow blades: offset darker copies for 3D thickness illusion ──
	const shadowBlades = generateBlades(
		BLADE_COUNT,
		(3 * Math.PI) / 180,
		0.85,
		"outer",
	);
	const innerShadowBlades = generateBlades(
		INNER_BLADE_COUNT,
		(6 * Math.PI) / 180,
		0.75,
		"inner",
	);
	const microShadowBlades = generateBlades(
		MICRO_BLADE_COUNT,
		(6 * Math.PI) / 180,
		0.65,
		"micro",
	);

	// ── Deep shadow blades: 2nd depth row, even more offset ──
	const deepShadowBlades = generateBlades(
		BLADE_COUNT,
		(6 * Math.PI) / 180,
		0.95,
		"outer",
	);
	const innerDeepShadowBlades = generateBlades(
		INNER_BLADE_COUNT,
		(12 * Math.PI) / 180,
		0.55,
		"inner",
	);

	// ── Seeded PRNG ─────────────────────────────────────────────────
	function mulberry32(a: number) {
		return () => {
			a |= 0;
			a = (a + 0x6d2b79f5) | 0;
			let t = Math.imul(a ^ (a >>> 15), 1 | a);
			t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
			return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
		};
	}
	const rng = mulberry32(42);
	const rand = (lo: number, hi: number) => lo + rng() * (hi - lo);

	// ── Plasma Energy Vortex: Differential rotation inward-suction disk ──
	// 5 concentric bands; band 0 = innermost (spins fastest)
	const TENDRIL_COUNT = 42;
	const ARM_COUNT = 6;
	const RADIAL_BANDS = 5;

	// 30 keyframes = smooth chaotic jitter
	const KF = 30;

	interface Tendril {
		frames: string; // semicolon-joined path keyframes
		d0: string; // first frame (static fallback)
		opacity: number;
		innerR: number; // hub radius (used for band assignment)
		band: number; // 0=innermost (fastest), 4=outermost (slowest)
		ondulDur: string;
		glowStroke: number;
		gradId: string;
		c1: string;
		c2: string;
		c3: string;
	}
	const tendrils: Tendril[] = [];

	// PromptForge brand plasma palette — electric cyan / deep purple / hot fuchsia
	const COLORS = [
		// Electric cyan → deep indigo (brand core)
		["#00ffff", "#6366f1", "#0d0030"],
		["#00e5ff", "#4f46e5", "#060025"],
		["#22d3ee", "#7c3aed", "#0a0030"],
		// Hot fuchsia → deep purple (energetic plasma)
		["#ff00ff", "#9333ea", "#1a0040"],
		["#ff33cc", "#7c3aed", "#120030"],
		["#e879f9", "#6d28d9", "#0e0028"],
		// Violet → dark indigo (depth / shadow)
		["#c084fc", "#4338ca", "#06001e"],
		["#a78bfa", "#3730a3", "#050018"],
		// Cyan-magenta hybrids (transition energy)
		["#67e8f9", "#a21caf", "#0e0030"],
		["#f0abfc", "#6366f1", "#0a0025"],
	];

	for (let i = 0; i < TENDRIL_COUNT; i++) {
		// Distribute across arms with some random scatter
		const armIndex = i % ARM_COUNT;
		const armBaseAngle = (armIndex / ARM_COUNT) * PI2 + rand(-0.3, 0.3);

		// Assign to a radial band — determines revolution speed
		// Band 0 = close to hub (very fast spin), Band 4 = far out (slow spin)
		const band = Math.floor(rng() * RADIAL_BANDS);
		// Hub radius: inner bands start closer to center
		const innerR = OUTER_R * (0.85 + band * 0.04) + rand(-3, 3);
		// Outer reach: highly varied so arms have very different lengths
		const outerR = innerR + rand(60, 420) * (1 + rng() * 0.8);

		// Width & opacity: purely random with some depth bias
		const maxWidth = rand(15, 95);
		const opacity = rand(0.25, 1.0);
		const glowStroke = rand(2, 8);

		// Fully random per-tendril color from palette
		const palette = COLORS[Math.floor(rng() * COLORS.length)];
		const c1 = palette[0];
		const c2 = palette[1];
		const c3 = palette[2];

		// --- CRITICAL: Galaxy arm geometry ---
		// For "sucked inward" look, the arm must TRAIL behind the spin.
		// The disc rotates CW (negative direction in SVG).
		// So: from hub (t=0) tip (t=1), the angle must INCREASE in the +θ direction
		// (CCW). This way, following the arm from tip→hub traces the spin direction,
		// making it look like the tip is being dragged toward the core.
		const spiralCurve = rand(1.0, 3.5); // sweep amount [radians]
		const spiralPow = rand(0.6, 1.1); // curvature distribution

		// Oscillation/jitter: smallish so arms stay readable
		const jitterAmp = rand(5, 18);
		// Each tendril has a unique flow speed (faster = more turbulent feel)
		const flowSpeed = rand(1.4, 4.0).toFixed(1);

		const N = 38;
		const keyframes: string[] = [];

		const jF1 = rand(3, 7);
		const jF2 = rand(8, 14);
		const jF3 = rand(15, 25);

		for (let kf = 0; kf < KF; kf++) {
			const time = kf / KF;
			// inwardPhase: drives the visual flow of energy patterns toward t=0 (hub)
			const inwardPhase = time * PI2 * 3.5;

			const left: string[] = [];
			const right: string[] = [];

			for (let s = 0; s <= N; s++) {
				const t = s / N; // t=0: hub end, t=1: outer tip

				const r = innerR + (outerR - innerR) * t;

				// Galaxy arm trailing geometry:
				// angle grows with t (more sweep at the tip), so tip is ahead in angle
				// while hub is behind → the arm visually trails INTO the core
				const angle =
					armBaseAngle + spiralCurve * Math.pow(t, spiralPow);

				// Lateral oscillation envelope — smooth bell peaking mid-arm
				// Zero at both endpoints so paths always close smoothly
				const env = Math.pow(t * (1 - t), 0.6); // bell; max ~t=0.5

				// Inward-traveling multi-harmonic jitter
				const jitter =
					Math.sin(jF1 * PI2 * t - inwardPhase) * 0.5 +
					Math.sin(jF2 * PI2 * t - inwardPhase * 1.5) * 0.33 +
					Math.sin(jF3 * PI2 * t - inwardPhase * 2.3) * 0.17;

				const ondul = jitterAmp * env * jitter;

				// Width taper: thickest in the mid-inner region (t≈0.3), needle-thin at both ends
				// t^0.5 * (1-t)^1.2 peaks around t=0.3
				const taper = Math.pow(t, 0.5) * Math.pow(1 - t, 1.2);
				const halfW = maxWidth * taper;

				const perpX = -Math.sin(angle);
				const perpY = Math.cos(angle);
				const cx = r * Math.cos(angle) + perpX * ondul;
				const cy = r * Math.sin(angle) + perpY * ondul;

				left.push(`${f(cx + perpX * halfW)},${f(cy + perpY * halfW)}`);
				right.unshift(
					`${f(cx - perpX * halfW)},${f(cy - perpY * halfW)}`,
				);
			}
			keyframes.push(`M${left.join(" L")} L${right.join(" L")} Z`);
		}

		tendrils.push({
			frames: keyframes.join(";"),
			d0: keyframes[0],
			opacity,
			innerR,
			band,
			ondulDur: flowSpeed,
			glowStroke,
			gradId: `bl-tendril-grad-${i}`,
			c1,
			c2,
			c3,
		});
	}

	// Differential rotation: Band 0 (innermost) spins fastest, Band 4 slowest.
	// All bands rotate continuously CW (to=360 means one full CW revolution).
	const bandRotationDur = [12, 22, 34, 50, 72]; // slower, more majestic spin

	const tendrilsByBand: Tendril[][] = Array.from(
		{ length: RADIAL_BANDS },
		() => [],
	);
	for (const t of tendrils) tendrilsByBand[t.band].push(t);

	// ambient sparks generator — more particles, faster rate
	const sparks = Array.from({ length: 80 }, () => {
		const spread = OUTER_R * 2;
		return {
			x: -spread / 2 + Math.random() * spread,
			y: -spread / 2 + Math.random() * spread,
			r: 0.3 + Math.random() * 0.9,
			dur: 0.8 + Math.random() * 1.8,
			delay: Math.random() * 4,
			opacity: 0.2 + Math.random() * 0.7,
			isA: Math.random() > 0.5,
		};
	});

	// Sporadic Steam Particles (Vent effect)
	const steamParticles = Array.from({ length: 15 }, () => {
		const startX = (Math.random() - 0.5) * OUTER_R * 1.5;
		const startY = (Math.random() - 0.5) * OUTER_R * 1.5;
		// Drift outward and upward
		const endX =
			startX + (Math.random() > 0.5 ? 1 : -1) * (20 + Math.random() * 40);
		const endY = startY - (30 + Math.random() * 60);
		// Control points for a soft curved drift
		const cx = startX + (endX - startX) * (Math.random() * 1.5);
		const cy = startY + (endY - startY) * Math.random();

		return {
			path: `M ${f(startX)},${f(startY)} Q ${f(cx)},${f(cy)} ${f(endX)},${f(endY)}`,
			r: 6 + Math.random() * 12,
			dur: 6 + Math.random() * 8, // Very slow, lingering steam
			delay: Math.random() * 10,
			opacity: 0.1 + Math.random() * 0.25, // Extremely subtle
		};
	});
	// ── Ambient Particles: Sparks flying off the core ──
	const PARTICLE_COUNT = 15;
	interface Particle {
		cx: number;
		cy: number;
		r: number;
		color: string;
		dur: string;
		delay: string;
		path: string;
		opacity: number;
	}
	const particles: Particle[] = Array.from({ length: PARTICLE_COUNT }, () => {
		const startAngle = rand(0, PI2);
		const startR = rand(INNER_R, MID_R);
		const endR = rand(OUTER_R + 20, OUTER_R + 100);
		// Swirling outward path
		const endAngle = startAngle - rand(0.5, 2.5); // spin outwards direction

		const sweep = rand(0, 1) > 0.5 ? 1 : 0;
		const path = `M${f(startR * Math.cos(startAngle))},${f(startR * Math.sin(startAngle))} 
					  A ${endR} ${endR} 0 0 ${sweep} ${f(endR * Math.cos(endAngle))},${f(endR * Math.sin(endAngle))}`;

		return {
			cx: 0,
			cy: 0,
			r: rand(0.5, 2.5),
			color:
				rand(0, 1) > 0.4
					? "url(#bl-cyan-neon)"
					: "url(#bl-purple-neon)",
			dur: rand(1.5, 4.0).toFixed(1) + "s",
			delay: rand(0, 4.0).toFixed(1) + "s",
			path,
			opacity: rand(0.5, 1.0),
		};
	});
</script>

<svg
	bind:this={svgEl}
	class="w-full h-auto bl-logo"
	class:bl-forging={mode === "forging"}
	class:bl-complete={mode === "complete"}
	class:bl-wallpaper={wallpaper}
	viewBox="-250 -200 1500 1000"
	overflow="visible"
	xmlns="http://www.w3.org/2000/svg"
	role="img"
	aria-label="PromptForge — AI-Powered Prompt Optimization"
>
	<defs>
		<linearGradient id="bl-cyan-neon" x1="0%" y1="0%" x2="100%" y2="0%">
			<stop offset="0%" stop-color="#00e5ff" />
			<stop offset="100%" stop-color="#80ffff" />
		</linearGradient>
		<linearGradient id="bl-purple-neon" x1="0%" y1="0%" x2="100%" y2="0%">
			<stop offset="0%" stop-color="#a855f7" />
			<stop offset="100%" stop-color="#d080ff" />
		</linearGradient>

		<!-- 3D depth gradients -->
		<radialGradient
			id="bl-nacelle-depth"
			cx="0"
			cy="0"
			r={OUTER_R}
			gradientUnits="userSpaceOnUse"
		>
			<stop offset="0%" stop-color="#020206" />
			<stop offset="45%" stop-color="#060612" />
			<stop offset="75%" stop-color="#0a0a18" />
			<stop offset="100%" stop-color="#0a0a18" stop-opacity="0" />
		</radialGradient>
		<radialGradient
			id="bl-nacelle-deep"
			cx="0"
			cy="0"
			r={OUTER_R}
			gradientUnits="userSpaceOnUse"
		>
			<stop offset="0%" stop-color="#010103" />
			<stop offset="35%" stop-color="#030308" />
			<stop offset="70%" stop-color="#060610" />
			<stop offset="100%" stop-color="#060610" stop-opacity="0" />
		</radialGradient>
		<!-- Blade surface: dark at hub → bright at tips (key 3D cue) -->
		<radialGradient
			id="bl-blade-surface"
			cx="0"
			cy="0"
			r={OUTER_R}
			gradientUnits="userSpaceOnUse"
		>
			<stop offset="0%" stop-color="#003848" />
			<stop offset="30%" stop-color="#006878" />
			<stop offset="65%" stop-color="#00b8d8" />
			<stop offset="100%" stop-color="#00e5ff" />
		</radialGradient>
		<!-- Shadow blade fills for two depth layers -->
		<linearGradient id="bl-blade-shadow" x1="0%" y1="0%" x2="100%" y2="0%">
			<stop offset="0%" stop-color="#005060" />
			<stop offset="100%" stop-color="#003848" />
		</linearGradient>
		<radialGradient
			id="bl-blade-deep"
			cx="0"
			cy="0"
			r={OUTER_R}
			gradientUnits="userSpaceOnUse"
		>
			<stop offset="0%" stop-color="#001820" />
			<stop offset="50%" stop-color="#002830" />
			<stop offset="100%" stop-color="#003040" />
		</radialGradient>
		<!-- Rim specular: bright spot for reflective metal -->
		<linearGradient
			id="bl-rim-specular"
			x1="20%"
			y1="0%"
			x2="80%"
			y2="100%"
		>
			<stop offset="0%" stop-color="#c0ffff" stop-opacity="0.5" />
			<stop offset="25%" stop-color="#80ffff" stop-opacity="0.15" />
			<stop offset="50%" stop-color="#003040" stop-opacity="0" />
			<stop offset="100%" stop-color="#003040" stop-opacity="0" />
		</linearGradient>
		<!-- Beam fade: now inverted (dim/cyan at base -> intense white/cyan at top) -->
		<linearGradient
			id="bl-beam-fade"
			gradientUnits="userSpaceOnUse"
			x1="0"
			y1="-50"
			x2="350"
			y2="-500"
		>
			<!-- Wide soft ambient: almost transparent at base, brilliant at tip -->
			<stop offset="0%" stop-color="#00e5ff" stop-opacity="0.05" />
			<stop offset="25%" stop-color="#00e5ff" stop-opacity="0.3" />
			<stop offset="60%" stop-color="#00f0ff" stop-opacity="0.7" />
			<stop offset="100%" stop-color="#80ffff" stop-opacity="1" />
		</linearGradient>
		<linearGradient
			id="bl-beam-fade-hot"
			gradientUnits="userSpaceOnUse"
			x1="0"
			y1="-30"
			x2="330"
			y2="-480"
		>
			<stop offset="0%" stop-color="#80ffff" stop-opacity="0.2" />
			<stop offset="40%" stop-color="#d0ffff" stop-opacity="0.8" />
			<stop offset="100%" stop-color="#ffffff" stop-opacity="1" />
		</linearGradient>

		<!-- Dynamic Tendril Gradients -->
		{#each tendrils as tendril}
			<radialGradient
				id={tendril.gradId}
				cx="0"
				cy="0"
				r={tendril.innerR * 10}
				gradientUnits="userSpaceOnUse"
			>
				<!-- Hot luminous core → rich brand mid → indigo void -->
				<stop offset="0%" stop-color={tendril.c1} stop-opacity="1" />
				<stop offset="15%" stop-color={tendril.c1} stop-opacity="0.9" />
				<stop offset="50%" stop-color={tendril.c2} stop-opacity="0.7" />
				<stop
					offset="85%"
					stop-color={tendril.c3}
					stop-opacity="0.25"
				/>
				<stop offset="100%" stop-color={tendril.c3} stop-opacity="0" />
			</radialGradient>
		{/each}

		<radialGradient
			id="bl-lens-outer"
			cx="0"
			cy="0"
			r={INNER_R * 0.45}
			gradientUnits="userSpaceOnUse"
		>
			<stop offset="50%" stop-color="#001828" stop-opacity="0" />
			<stop offset="90%" stop-color="#003550" stop-opacity="0.8" />
			<stop offset="100%" stop-color="#005075" stop-opacity="1" />
		</radialGradient>

		<!-- Solid Metal Cylinder Lighting (Bright Steel Tone for High Visibility) -->
		<linearGradient id="bl-cyl-outer-grad" x1="0" y1="0" x2="1" y2="1">
			<stop offset="0%" stop-color="#142f4c" />
			<stop offset="25%" stop-color="#2a4e76" />
			<stop offset="50%" stop-color="#0e243a" />
			<stop offset="100%" stop-color="#030b14" />
		</linearGradient>

		<linearGradient id="bl-cyl-inner-grad" x1="0" y1="0" x2="1" y2="1">
			<stop offset="0%" stop-color="#102a4a" />
			<stop offset="40%" stop-color="#06121e" />
			<stop offset="100%" stop-color="#01060a" />
		</linearGradient>

		<radialGradient id="bl-cyl-base-grad" cx="0" cy="0" r="100%">
			<stop offset="50%" stop-color="#04121c" />
			<stop offset="100%" stop-color="#0a1d30" />
		</radialGradient>

		<radialGradient
			id="bl-lens-inner"
			cx="0"
			cy="0"
			r="11"
			gradientUnits="userSpaceOnUse"
		>
			<stop offset="0%" stop-color="#000000" stop-opacity="0" />
			<stop offset="80%" stop-color="#0080aa" stop-opacity="0.6" />
			<stop offset="100%" stop-color="#00d0ff" stop-opacity="1" />
		</radialGradient>

		<!-- Horizontal light flare at the beam origin -->
		<radialGradient id="bl-core-flare" cx="50%" cy="50%" r="50%">
			<stop offset="0%" stop-color="#ffffff" stop-opacity="1" />
			<stop offset="20%" stop-color="#80ffff" stop-opacity="0.8" />
			<stop offset="60%" stop-color="#00e5ff" stop-opacity="0.3" />
			<stop offset="100%" stop-color="#00e5ff" stop-opacity="0" />
		</radialGradient>

		<!-- Inner shadow filter for nacelle rim -->
		<filter
			id="bl-inner-shadow"
			x="-20%"
			y="-20%"
			width="140%"
			height="140%"
		>
			<feGaussianBlur in="SourceAlpha" stdDeviation="4" result="shadow" />
			<feComposite
				in="shadow"
				in2="SourceAlpha"
				operator="arithmetic"
				k2="-1"
				k3="1"
				result="inner"
			/>
			<feFlood flood-color="#000818" flood-opacity="0.7" result="color" />
			<feComposite
				in="color"
				in2="inner"
				operator="in"
				result="innerShadow"
			/>
			<feMerge>
				<feMergeNode in="innerShadow" />
				<feMergeNode in="SourceGraphic" />
			</feMerge>
		</filter>

		<radialGradient
			id="bl-hub-depth"
			cx="0"
			cy="0"
			r={INNER_R}
			gradientUnits="userSpaceOnUse"
		>
			<stop offset="0%" stop-color="#000000" />
			<stop offset="30%" stop-color="#020815" />
			<stop offset="70%" stop-color="#04101e" />
			<stop offset="100%" stop-color="#002030" />
		</radialGradient>

		<filter id="bl-cyan-glow" x="-50%" y="-50%" width="200%" height="200%">
			<feGaussianBlur stdDeviation={cyanBlur} result="coloredBlur" />
			<feMerge>
				<feMergeNode in="coloredBlur" />
				<feMergeNode in="SourceGraphic" />
			</feMerge>
		</filter>
		<filter id="bl-beam-glow" x="-50%" y="-50%" width="200%" height="200%">
			<feGaussianBlur stdDeviation={beamBlur} result="coloredBlur" />
			<feMerge>
				<feMergeNode in="coloredBlur" />
				<feMergeNode in="coloredBlur" />
				<feMergeNode in="SourceGraphic" />
			</feMerge>
		</filter>
		<!-- Ultra-wide ambient beam bloom (perpendicular Gaussian spread) -->
		<filter id="bl-beam-wide" x="-400%" y="-20%" width="900%" height="140%">
			<feGaussianBlur stdDeviation="45" />
		</filter>
		<!-- Mid glow corona (perpendicular Gaussian spread) -->
		<filter id="bl-beam-mid" x="-150%" y="-20%" width="400%" height="140%">
			<feGaussianBlur stdDeviation="12" />
		</filter>

		<!-- Heavy Blur for Venting Steam -->
		<filter
			id="bl-steam-blur"
			x="-100%"
			y="-100%"
			width="300%"
			height="300%"
		>
			<feGaussianBlur stdDeviation="8" />
		</filter>
	</defs>

	<g transform="translate({CX}, {CY})">
		<!-- ═══ 3D CYLINDER BODY ═══ -->
		<!-- Draw the cylinder body by connecting the back face to the front face -->
		<g>
			<!-- Cylinder outer wall -->
			<path
				d="
				M {CYL_DX + OUTER_R * Math.cos(CYL_ANGLE + Math.PI / 2)} {CYL_DY +
					OUTER_R * Math.sin(CYL_ANGLE + Math.PI / 2)}
				L {OUTER_R * Math.cos(CYL_ANGLE + Math.PI / 2)} {OUTER_R *
					Math.sin(CYL_ANGLE + Math.PI / 2)}
				A {OUTER_R} {OUTER_R} 0 0 0 {OUTER_R *
					Math.cos(CYL_ANGLE - Math.PI / 2)} {OUTER_R *
					Math.sin(CYL_ANGLE - Math.PI / 2)}
				L {CYL_DX + OUTER_R * Math.cos(CYL_ANGLE - Math.PI / 2)} {CYL_DY +
					OUTER_R * Math.sin(CYL_ANGLE - Math.PI / 2)}
				A {OUTER_R} {OUTER_R} 0 0 1 {CYL_DX +
					OUTER_R * Math.cos(CYL_ANGLE + Math.PI / 2)} {CYL_DY +
					OUTER_R * Math.sin(CYL_ANGLE + Math.PI / 2)}
				Z
			"
				fill="url(#bl-cyl-outer-grad)"
				stroke="#001a26"
				stroke-width="1.5"
			/>

			<!-- Cylinder inner wall (visible part) -->
			<path
				d="
				M {CYL_DX + OUTER_R * Math.cos(CYL_ANGLE - Math.PI / 2)} {CYL_DY +
					OUTER_R * Math.sin(CYL_ANGLE - Math.PI / 2)}
				L {OUTER_R * Math.cos(CYL_ANGLE - Math.PI / 2)} {OUTER_R *
					Math.sin(CYL_ANGLE - Math.PI / 2)}
				A {OUTER_R} {OUTER_R} 0 0 1 {OUTER_R *
					Math.cos(CYL_ANGLE + Math.PI / 2)} {OUTER_R *
					Math.sin(CYL_ANGLE + Math.PI / 2)}
				L {CYL_DX + OUTER_R * Math.cos(CYL_ANGLE + Math.PI / 2)} {CYL_DY +
					OUTER_R * Math.sin(CYL_ANGLE + Math.PI / 2)}
				A {OUTER_R} {OUTER_R} 0 0 0 {CYL_DX +
					OUTER_R * Math.cos(CYL_ANGLE - Math.PI / 2)} {CYL_DY +
					OUTER_R * Math.sin(CYL_ANGLE - Math.PI / 2)}
				Z
			"
				fill="url(#bl-cyl-inner-grad)"
			/>

			<!-- Latitudinal Cylinder Arcs (Belly Detail Rings) -->
			<g filter="url(#bl-cyan-glow)">
				{#each latArcs as arcCmd}
					<!-- Glow layer -->
					<path
						d={arcCmd}
						stroke="url(#bl-cyan-neon)"
						stroke-width="3"
						fill="none"
						opacity="0.8"
					/>
					<!-- Core layer -->
					<path
						d={arcCmd}
						stroke="#ffffff"
						stroke-width="1.5"
						fill="none"
						opacity="0.9"
					/>
				{/each}

				<!-- Bottom casing cutouts (straight lines along the belly) -->
				<path
					d="
						M {CYL_DX * 0.1 + OUTER_R * Math.cos(CYL_ANGLE)} {CYL_DY * 0.1 +
						OUTER_R * Math.sin(CYL_ANGLE)}
						L {CYL_DX * 0.9 + OUTER_R * Math.cos(CYL_ANGLE)} {CYL_DY * 0.9 +
						OUTER_R * Math.sin(CYL_ANGLE)}
					"
					stroke="url(#bl-cyan-neon)"
					stroke-width="2.5"
					fill="none"
					opacity="0.9"
				/>
				<path
					d="
						M {CYL_DX * 0.15 + OUTER_R * Math.cos(CYL_ANGLE + 0.2)} {CYL_DY * 0.15 +
						OUTER_R * Math.sin(CYL_ANGLE + 0.2)}
						L {CYL_DX * 0.85 + OUTER_R * Math.cos(CYL_ANGLE + 0.2)} {CYL_DY * 0.85 +
						OUTER_R * Math.sin(CYL_ANGLE + 0.2)}
					"
					stroke="url(#bl-cyan-neon)"
					stroke-width="1.5"
					fill="none"
					opacity="0.6"
				/>
				<path
					d="
						M {CYL_DX * 0.15 + OUTER_R * Math.cos(CYL_ANGLE - 0.2)} {CYL_DY * 0.15 +
						OUTER_R * Math.sin(CYL_ANGLE - 0.2)}
						L {CYL_DX * 0.85 + OUTER_R * Math.cos(CYL_ANGLE - 0.2)} {CYL_DY * 0.85 +
						OUTER_R * Math.sin(CYL_ANGLE - 0.2)}
					"
					stroke="url(#bl-cyan-neon)"
					stroke-width="1.5"
					fill="none"
					opacity="0.6"
				/>
			</g>

			<!-- Back face rim (The floor of the socket) -->
			<circle
				cx={CYL_DX}
				cy={CYL_DY}
				r={OUTER_R}
				stroke="#000a12"
				stroke-width="3"
				fill="url(#bl-cyl-base-grad)"
			/>
			<circle
				cx={CYL_DX}
				cy={CYL_DY}
				r={OUTER_R}
				stroke="url(#bl-cyan-neon)"
				stroke-width="1"
				fill="none"
				opacity="0.5"
			/>
		</g>

		<!-- Purple Plasma Vortex: Differential rotation black hole suction -->
		<!-- Each band rotates at a different speed: inner=fast, outer=slow -->
		<!-- screen blending creates optical glow at intersections -->
		<g style="mix-blend-mode: screen;">
			{#each tendrilsByBand as band, bi}
				<!-- Each concentric band spins continuously at its own speed -->
				<g>
					<animateTransform
						attributeName="transform"
						type="rotate"
						from="0"
						to="-360"
						dur="{bandRotationDur[bi]}s"
						repeatCount="indefinite"
					/>
					<!-- Sub-glow bloom layer -->
					{#each band as tendril}
						<path
							d={tendril.d0}
							fill="url(#{tendril.gradId})"
							opacity={tendril.opacity * 0.12}
							stroke="url(#{tendril.gradId})"
							stroke-width={tendril.glowStroke * 2.5}
							stroke-linejoin="round"
							filter="url(#bl-cyan-glow)"
						>
							<animate
								attributeName="d"
								values={tendril.frames}
								dur="{tendril.ondulDur}s"
								repeatCount="indefinite"
							/>
						</path>
					{/each}
					<!-- Sharp core lightning -->
					{#each band as tendril}
						<path
							d={tendril.d0}
							fill="url(#{tendril.gradId})"
							opacity={tendril.opacity}
							stroke="#fff"
							stroke-width="0.8"
							stroke-opacity={tendril.opacity * 0.5}
							stroke-linejoin="round"
						>
							<animate
								attributeName="d"
								values={tendril.frames}
								dur="{tendril.ondulDur}s"
								repeatCount="indefinite"
							/>
						</path>
					{/each}
				</g>
			{/each}
		</g>

		<!-- Ambient Spark Particles -->
		<g>
			{#each particles as p}
				<circle r={p.r} fill={p.color} opacity="0">
					<animateMotion
						path={p.path}
						dur={p.dur}
						begin={p.delay}
						repeatCount="indefinite"
					/>
					<animate
						attributeName="opacity"
						values="0; {p.opacity}; {p.opacity * 0.5}; 0"
						keyTimes="0; 0.1; 0.6; 1"
						dur={p.dur}
						begin={p.delay}
						repeatCount="indefinite"
					/>
					<animateTransform
						attributeName="transform"
						type="scale"
						values="0; 1.5; 1; 0"
						keyTimes="0; 0.1; 0.6; 1"
						dur={p.dur}
						begin={p.delay}
						repeatCount="indefinite"
					/>
				</circle>
			{/each}
		</g>

		<!-- ═══ 3D TURBINE: layered depth illusion ═══ -->
		<g>
			<!-- Tightly framed Case Flanges (Brightened) -->
			<!-- Edge highlight ring hugging the exact boundary -->
			<animateTransform
				attributeName="transform"
				type="rotate"
				from="0"
				to="-360"
				dur={coreDur}
				repeatCount="indefinite"
			/>

			<!-- Layer 0: Deep nacelle void — blackest depth behind everything -->
			<circle r={OUTER_R - 2} fill="url(#bl-nacelle-deep)" />

			<!-- Layer 1: Nacelle depth rings — concentric recession lines -->
			{#each [0.85, 0.65, 0.45] as pct}
				<circle
					r={INNER_R + (OUTER_R - INNER_R) * pct}
					stroke="#0a1525"
					stroke-width="1.5"
					fill="none"
					opacity={0.3 + (1 - pct) * 0.3}
				/>
			{/each}

			<!-- Layer 2: Deep shadow blades — solid fills -->
			{#each deepShadowBlades as blade}
				<path d={blade} fill="#000609" opacity="0.6" />
			{/each}

			<!-- Layer 3: Nacelle depth disc — mid-depth darkness -->
			<circle
				r={OUTER_R - 4}
				fill="url(#bl-nacelle-depth)"
				opacity="0.8"
			/>

			<!-- Layer 4: Shadow blades — solid fills -->
			{#each shadowBlades as blade}
				<path d={blade} fill="#000d14" opacity="0.8" />
			{/each}

			<g filter="url(#bl-cyan-glow)">
				<!-- Layer 5: Main blades — solid metallic overlapping fans -->
				{#each blades as blade}
					<path
						d={blade}
						fill="url(#bl-blade-surface)"
						opacity="0.95"
					/>
				{/each}
				<!-- Layer 6: Blade edge sharp highlighting -->
				{#each blades as blade}
					<path
						d={blade}
						fill="none"
						stroke="#c0ffff"
						stroke-width="1.2"
						opacity="0.6"
					/>
				{/each}
			</g>

			<!-- Layer 7: Inner rim shadow — dark band where blades meet housing -->
			<circle
				r={OUTER_R - 5}
				stroke="#000810"
				stroke-width="8"
				fill="none"
				opacity="0.35"
			/>

			<!-- Layer 8: Outer rim bevel — thick cylindrical housing -->
			<circle
				r={OUTER_R + 1}
				stroke="#001820"
				stroke-width="3"
				fill="none"
				opacity="0.5"
			/>
			<circle r={OUTER_R} stroke="#003040" stroke-width="6" fill="none" />
			<circle
				r={OUTER_R}
				stroke="url(#bl-cyan-neon)"
				stroke-width="3.5"
				fill="none"
			/>
			<circle
				r={OUTER_R}
				stroke="#b0ffff"
				stroke-width="1"
				fill="none"
				opacity="0.45"
			/>
			<circle
				r={OUTER_R - 1}
				stroke="#b0ffff"
				stroke-width="0.5"
				fill="none"
				opacity="0.2"
			/>

			<!-- Layer 9: Rim specular highlight — reflective metal glint -->
			<circle
				r={OUTER_R}
				stroke="url(#bl-rim-specular)"
				stroke-width="4"
				fill="none"
			/>
		</g>

		<!-- Mid ring: CCW counter-rotation, beveled -->
		<g>
			<animateTransform
				attributeName="transform"
				type="rotate"
				from="0"
				to="360"
				dur={coreDur}
				repeatCount="indefinite"
			/>
			<circle
				r={MID_R + 1}
				stroke="#001820"
				stroke-width="3"
				fill="none"
				opacity="0.3"
			/>
			<circle
				r={MID_R}
				stroke="#003040"
				stroke-width="4.5"
				fill="none"
				filter="url(#bl-cyan-glow)"
			/>
			<circle
				r={MID_R}
				stroke="url(#bl-cyan-neon)"
				stroke-width="2.5"
				fill="none"
				filter="url(#bl-cyan-glow)"
			/>
			<circle
				r={MID_R}
				stroke="#b0ffff"
				stroke-width="1.2"
				fill="none"
				opacity="0.65"
			/>
			<circle
				r={MID_R - 1}
				stroke="#b0ffff"
				stroke-width="0.5"
				fill="none"
				opacity="0.4"
			/>

			<!-- Layer 2: Deep inner shadow blades (+15°) -->
			{#each innerDeepShadowBlades as blade}
				<path d={blade} fill="url(#bl-blade-deep)" opacity="0.45" />
			{/each}

			<!-- Layer 4: Inner shadow blades (+8°) -->
			{#each innerShadowBlades as blade}
				<path d={blade} fill="url(#bl-blade-shadow)" opacity="0.5" />
			{/each}

			<g filter="url(#bl-cyan-glow)">
				<!-- Layer 5: Inner main blades -->
				{#each innerBlades as blade}
					<path
						d={blade}
						fill="url(#bl-blade-surface)"
						opacity="0.95"
					/>
				{/each}
				<!-- Layer 6: Inner blade leading edges -->
				{#each innerBlades as blade}
					<path
						d={blade}
						fill="none"
						stroke="#b0ffff"
						stroke-width="1.2"
						opacity="0.55"
					/>
				{/each}
			</g>
		</g>

		<!-- Hub: deep layered mechanical socket -->
		<g filter="url(#bl-inner-shadow)">
			<circle r={INNER_R} fill="url(#bl-hub-depth)" />
		</g>

		<!-- Spinning Data Rings (dashed tech lines) -->
		<g>
			<animateTransform
				attributeName="transform"
				type="rotate"
				from="360"
				to="0"
				dur="8s"
				repeatCount="indefinite"
			/>
			<circle
				r={INNER_R * 0.85}
				stroke="#00e5ff"
				stroke-width="0.8"
				stroke-dasharray="2 4 8 4"
				fill="none"
				opacity="0.3"
			/>
			<circle
				r={INNER_R * 0.75}
				stroke="#a855f7"
				stroke-width="1.2"
				stroke-dasharray="1 6"
				fill="none"
				opacity="0.4"
			/>
		</g>

		<!-- Micro Turbine Layer (Clockwise inner spin) -->
		<g>
			<animateTransform
				attributeName="transform"
				type="rotate"
				from="0"
				to="-360"
				dur="12s"
				repeatCount="indefinite"
			/>
			<!-- Depth shadow base -->
			<circle r={INNER_R * 0.65} fill="#020205" opacity="0.8" />

			<!-- Shadow micro blades -->
			{#each microShadowBlades as blade}
				<path d={blade} fill="url(#bl-blade-deep)" opacity="0.6" />
			{/each}

			<g filter="url(#bl-cyan-glow)">
				<!-- Main micro blades -->
				{#each microBlades as blade}
					<path
						d={blade}
						fill="url(#bl-blade-surface)"
						opacity="0.9"
					/>
				{/each}
				<!-- Micro blade highlights -->
				{#each microBlades as blade}
					<path
						d={blade}
						fill="none"
						stroke="#ffffff"
						stroke-width="0.6"
						opacity="0.6"
					/>
				{/each}
			</g>
		</g>

		<!-- Inner socket structure lines -->
		<circle r={INNER_R * 0.45} fill="url(#bl-lens-outer)" />
		<circle
			r={INNER_R * 0.45}
			stroke="#0a2a40"
			stroke-width="1.5"
			fill="none"
			opacity="0.8"
		/>

		<!-- Center solid physical geometry -->
		<circle r="14" fill="#01060a" stroke="#005070" stroke-width="0.5" />
		<circle r="11" fill="url(#bl-lens-inner)" />

		<!-- Inner ring collar stroke on top of the hub fill -->
		<circle r={INNER_R} stroke="#003040" stroke-width="5" fill="none" />
		<circle
			r={INNER_R}
			stroke="url(#bl-cyan-neon)"
			stroke-width="3.5"
			fill="none"
			filter="url(#bl-cyan-glow)"
			opacity="0.8"
		/>
		<circle
			r={INNER_R}
			stroke="#ffffff"
			stroke-width="0.8"
			fill="none"
			opacity="0.6"
		/>

		<!-- Center dot glow socket -->
		<g class="bl-core-pulse">
			<circle
				r="7"
				fill="#00e5ff"
				filter="url(#bl-cyan-glow)"
				opacity="0.6"
			/>
			<circle r="4" fill="#ffffff" filter="url(#bl-beam-glow)" />
		</g>

		<!-- Forge beam — Compounded Additive Energy Flow -->
		<!-- Layer 0: Core origin flare (horizontal burst) -->
		<ellipse
			cx="0"
			cy="0"
			rx="55"
			ry="16"
			fill="url(#bl-core-flare)"
			transform="rotate(-53.5)"
			class="bl-beam-hum"
			style="mix-blend-mode: screen;"
			opacity="0.9"
		/>

		<!-- Cross-section glow: each layer is a thin line + Gaussian blur.             -->
		<!-- The blur spreads as a natural bell-curve — bright at center, transparent at edges. -->
		<!-- No tube rings: opacity comes from the blur math, not the stroke width.     -->
		<g style="mix-blend-mode: screen;">
			<!-- L1: Ultra-wide ambient halo — 4px cyan, blurred ±45px -->
			<path
				class="bl-beam-hum"
				d="M0 0 L350 -500"
				stroke="#00c0e0"
				stroke-width="4"
				opacity="0.85"
				stroke-linecap="round"
				filter="url(#bl-beam-wide)"
			/>
			<!-- L2: Mid glow corona — 4px, blurred ±12px -->
			<path
				class="bl-beam-hum"
				d="M0 0 L350 -500"
				stroke="#00e8ff"
				stroke-width="4"
				opacity="0.9"
				stroke-linecap="round"
				filter="url(#bl-beam-mid)"
			/>
			<!-- L3: Core bloom — 5px bright cyan, small glow blur -->
			<path
				class="bl-beam-hum"
				d="M0 0 L350 -500"
				stroke="#80ffff"
				stroke-width="5"
				opacity="1"
				stroke-linecap="round"
				filter="url(#bl-beam-glow)"
			/>
			<!-- L4: Animated energy dashes flowing upward -->
			<path
				d="M0 0 L350 -500"
				stroke="#c0ffff"
				stroke-width="3"
				stroke-linecap="round"
				stroke-dasharray="80 130"
				class="bl-beam-flow"
			/>
			<!-- L5: Razor-thin blazing white spine -->
			<path
				class="bl-beam-hum"
				d="M0 0 L340 -490"
				stroke="#ffffff"
				stroke-width="2"
				opacity="1"
				stroke-linecap="round"
			/>
		</g>

		<!-- Subdued Sporadic Steam Vents -->
		{#if mode === "forging"}
			<g filter="url(#bl-steam-blur)" opacity="0.6">
				{#each steamParticles as p}
					<circle r={p.r} fill="#80c0ff">
						<animateMotion
							path={p.path}
							dur="{p.dur}s"
							begin="{p.delay}s"
							repeatCount="indefinite"
						/>
						<animate
							attributeName="opacity"
							values="0; {p.opacity}; {p.opacity}; 0"
							keyTimes="0; 0.2; 0.6; 1"
							dur="{p.dur}s"
							begin="{p.delay}s"
							repeatCount="indefinite"
						/>
						<!-- Steam cloud expands as it drifts -->
						<animateTransform
							attributeName="transform"
							type="scale"
							values="0.5; 1.5; 2.5"
							keyTimes="0; 0.5; 1"
							dur="{p.dur}s"
							begin="{p.delay}s"
							repeatCount="indefinite"
						/>
					</circle>
				{/each}
			</g>
		{/if}
	</g>

	<!-- Text (hidden in wallpaper mode) -->
	{#if !wallpaper}
	<g
		transform="translate({CX}, 610)"
		text-anchor="middle"
		font-family="Syne, sans-serif"
	>
		<text
			x="0"
			y="0"
			font-size="64"
			font-weight="900"
			letter-spacing="4"
			fill="url(#bl-cyan-neon)"
			opacity="0.6"
			stroke="url(#bl-cyan-neon)"
			stroke-width="12"
			stroke-linejoin="round"
			filter="url(#bl-cyan-glow)">PROMPTFORGE</text
		>
		<text
			x="0"
			y="42"
			font-size="26"
			font-weight="700"
			letter-spacing="3"
			fill="url(#bl-purple-neon)"
			opacity="0.7"
			stroke="url(#bl-purple-neon)"
			stroke-width="8"
			stroke-linejoin="round">AI-POWERED PROMPT OPTIMIZATION</text
		>

		<text
			class="bl-title {titleClass}"
			x="0"
			y="0"
			font-size="64"
			font-weight="900"
			letter-spacing="4"
			fill="#ffffff"
			stroke="url(#bl-cyan-neon)"
			stroke-width="1.5">PROMPTFORGE</text
		>
		<text
			x="0"
			y="42"
			font-size="26"
			font-weight="700"
			letter-spacing="3"
			fill="#f8e8ff"
			stroke="url(#bl-purple-neon)"
			stroke-width="0.5">AI-POWERED PROMPT OPTIMIZATION</text
		>
	</g>
	{/if}
</svg>

<style>
	/* ── Beam: always pulsating ── */
	.bl-beam-hum {
		animation: bl-hum 1.5s cubic-bezier(0.4, 0, 0.2, 1) infinite;
	}
	@keyframes bl-hum {
		0%,
		100% {
			opacity: 0.85;
			transform: scale(1) translateY(0);
		}
		50% {
			opacity: 1;
			transform: scale(1.02) translateY(-1px);
		}
	}

	/* ── Beam Flow: traveling energy dashes ── */
	.bl-beam-flow {
		animation: bl-flow 0.8s linear infinite;
	}
	@keyframes bl-flow {
		to {
			stroke-dashoffset: -200;
		}
	}

	/* ── Core vibration ── */
	.bl-core-pulse {
		animation: bl-vibrate 0.1s linear infinite;
	}
	@keyframes bl-vibrate {
		0%,
		100% {
			transform: translate(0, 0);
		}
		25% {
			transform: translate(0.5px, -0.5px);
		}
		50% {
			transform: translate(-0.5px, 0.5px);
		}
		75% {
			transform: translate(0.5px, 0.5px);
		}
	}

	/* ── Title shimmer ── */
	.bl-text-shimmer {
		animation: bl-shimmer 2s ease-out 1;
	}
	@keyframes bl-shimmer {
		0% {
			opacity: 0.6;
		}
		30% {
			opacity: 1;
		}
		60% {
			opacity: 0.85;
		}
		100% {
			opacity: 1;
		}
	}

	/* ── Entrance ── */
	.bl-logo {
		animation: bl-entrance 1.2s cubic-bezier(0.16, 1, 0.3, 1) both;
	}
	@keyframes bl-entrance {
		from {
			opacity: 0;
			transform: scale(0.92) translateY(15px);
		}
		to {
			opacity: 1;
			transform: scale(1) translateY(0);
		}
	}

	/* ── Wallpaper mode ── */
	.bl-wallpaper {
		opacity: 0.12;
		animation: none;
		width: 100%;
		height: 100%;
	}

	.bl-wallpaper .bl-beam-hum {
		animation-duration: 3s;
	}

	.bl-wallpaper .bl-beam-flow {
		animation-duration: 1.6s;
	}

	.bl-wallpaper .bl-core-pulse {
		animation-duration: 0.2s;
	}
</style>
