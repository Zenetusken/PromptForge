<script lang="ts">
	let { height, width }: { height?: number; width?: number } = $props();

	const CX = 46;
	const CY = 50;
	const INNER_R = 13;
	const OUTER_R = 36;
	const PI2 = Math.PI * 2;
	const f = (n: number) => n.toFixed(1);

	// 8 blades — visible gaps at icon scale
	const BLADE_COUNT = 8;
	const BLADE_SWEEP = (32 * Math.PI) / 180;

	const blades = Array.from({ length: BLADE_COUNT }, (_, i) => {
		const θ = (i / BLADE_COUNT) * PI2;
		const slotHalfW = (PI2 / BLADE_COUNT) * 0.3;
		const SAMPLES = 8;
		const leading: string[] = [];
		const trailing: string[] = [];

		for (let s = 0; s <= SAMPLES; s++) {
			const t = s / SAMPLES;
			const r = INNER_R + (OUTER_R - INNER_R) * t;
			const angle = θ + BLADE_SWEEP * Math.pow(t, 0.85);
			const halfW = slotHalfW * Math.pow(t, 0.75);

			leading.push(
				`${f(CX + r * Math.cos(angle + halfW))},${f(CY + r * Math.sin(angle + halfW))}`,
			);
			trailing.unshift(
				`${f(CX + r * Math.cos(angle - halfW))},${f(CY + r * Math.sin(angle - halfW))}`,
			);
		}

		return `M${leading.join(" L")} L${trailing.join(" L")} Z`;
	});
</script>

<svg
	{height}
	{width}
	viewBox="0 0 780 98"
	overflow="visible"
	xmlns="http://www.w3.org/2000/svg"
	role="img"
	aria-label="PromptForge"
>
	<defs>
		<linearGradient id="bm-cyan" x1="0%" y1="0%" x2="100%" y2="0%">
			<stop offset="0%" stop-color="#00e5ff" />
			<stop offset="100%" stop-color="#80ffff" />
		</linearGradient>
		<radialGradient
			id="bm-blade-fill"
			cx={CX}
			cy={CY}
			r={OUTER_R}
			gradientUnits="userSpaceOnUse"
		>
			<stop offset="0%" stop-color="#005868" />
			<stop offset="60%" stop-color="#00b0d0" />
			<stop offset="100%" stop-color="#00e5ff" />
		</radialGradient>

		<!-- Glow filter — replicates the hero SVG text bloom -->
		<filter id="bm-text-glow" x="-30%" y="-60%" width="160%" height="220%">
			<feGaussianBlur stdDeviation="3" result="coloredBlur" />
			<feMerge>
				<feMergeNode in="coloredBlur" />
				<feMergeNode in="SourceGraphic" />
			</feMerge>
		</filter>
	</defs>

	<!-- Turbine — no background disc, gaps between blades show page bg -->
	{#each blades as blade}
		<path d={blade} fill="url(#bm-blade-fill)" opacity="0.9" />
	{/each}

	<!-- Outer rim -->
	<circle
		cx={CX}
		cy={CY}
		r={OUTER_R}
		stroke="url(#bm-cyan)"
		stroke-width="2.5"
		fill="none"
	/>

	<!-- Hub -->
	<circle cx={CX} cy={CY} r={INNER_R} fill="#060610" />
	<circle
		cx={CX}
		cy={CY}
		r={INNER_R}
		stroke="url(#bm-cyan)"
		stroke-width="2"
		fill="none"
	/>

	<!-- Center dot -->
	<circle cx={CX} cy={CY} r="3.5" fill="url(#bm-cyan)" />

	<!-- Branded wordmark: two-layer text stack matching hero SVG style -->
	<g
		text-anchor="start"
		font-family="Syne, sans-serif"
		font-weight="900"
		font-size="64"
		letter-spacing="1"
	>
		<!-- Back layer: wide glow halo (cyan fill + thick cyan stroke + glow filter) -->
		<text
			x="102"
			y="70"
			fill="url(#bm-cyan)"
			opacity="0.55"
			stroke="url(#bm-cyan)"
			stroke-width="8"
			stroke-linejoin="round"
			filter="url(#bm-text-glow)">PROMPTFORGE</text
		>

		<!-- Front layer: crisp white fill with thin cyan stroke for the neon edge -->
		<text
			x="102"
			y="70"
			fill="#ffffff"
			stroke="url(#bm-cyan)"
			stroke-width="1.2">PROMPTFORGE</text
		>
	</g>
</svg>
