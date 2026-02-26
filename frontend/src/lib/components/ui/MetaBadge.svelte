<script lang="ts">
    import { Tooltip } from "./index";
    import {
        getStrategyColor,
        STRATEGY_LABELS,
        type StrategyName,
    } from "$lib/utils/strategies";
    import { getTaskTypeColor } from "$lib/utils/taskTypes";
    import { getComplexityColor } from "$lib/utils/complexity";

    let {
        type,
        value,
        variant = "text",
        size = "sm",
        showTooltip = true,
    }: {
        type: "strategy" | "task" | "tag" | "complexity";
        value: string | null | undefined;
        variant?: "text" | "pill" | "solid";
        size?: "sm" | "xs";
        showTooltip?: boolean;
    } = $props();

    // Common base classes for all badges
    const baseClasses =
        "font-mono tracking-wider items-center justify-center shrink-0 uppercase inline-flex";

    // Size specific classes
    const sizeClasses = {
        sm: "text-[10px] px-1.5 py-0.5",
        xs: "text-[9px] px-1 py-px",
    };

    let normalizedValue = $derived(value || "Unknown");

    // Get derived color classes based on the type
    let colorMeta = $derived(
        type === "strategy"
            ? getStrategyColor(value)
            : type === "complexity"
              ? getComplexityColor(value)
              : type === "tag"
                ? {
                      text: "text-neon-green",
                      border: "border-neon-green/30",
                      btnBg: "bg-transparent",
                      chipBg: "bg-transparent",
                  }
                : getTaskTypeColor(value),
    );

    // Get the display text. Strategies use a lookup table, tasks, complexity, and tags use the raw value
    let displayText = $derived(
        type === "strategy"
            ? (STRATEGY_LABELS[value as StrategyName] ?? normalizedValue)
            : type === "tag"
              ? `#${normalizedValue}`
              : normalizedValue,
    );

    // Tooltip text
    let tooltipText = $derived(
        type === "strategy"
            ? `Strategy: ${displayText}`
            : type === "tag"
              ? `Tag: ${normalizedValue}`
              : type === "complexity"
                ? `Complexity: ${displayText}`
                : `Task type: ${displayText}`,
    );

    // Task type is always rendered as plain borderless text — enforced here so
    // every call site picks it up automatically without needing to specify variant.
    let effectiveVariant = $derived(type === "task" ? "text" : variant);

    // Determine the component's final class based on the chosen variant
    let variantClass = $derived.by(() => {
        switch (effectiveVariant) {
            case "text":
                return `font-bold ${colorMeta.text}`;
            case "pill": {
                const borderFaint =
                    "border" in colorMeta
                        ? colorMeta.border
                        : "border-current/20";
                return `rounded-md font-semibold border ${borderFaint} bg-transparent ${colorMeta.text}`;
            }
            case "solid": {
                const borderStrong =
                    "border" in colorMeta
                        ? colorMeta.border.replace("-l-", "-")
                        : "border-current";
                return `rounded-full border pb-[1px] font-bold ${colorMeta.text} ${borderStrong} bg-transparent`;
            }
            default:
                return colorMeta.text;
        }
    });

    let finalClasses = $derived(`${baseClasses} ${sizeClasses[size]} ${variantClass}`);
</script>

{#if showTooltip}
    <Tooltip text={tooltipText}>
        <span class={finalClasses} data-testid="meta-badge-{type}">
            {displayText}
        </span>
    </Tooltip>
{:else}
    <span class={finalClasses} data-testid="meta-badge-{type}">
        {displayText}
    </span>
{/if}
