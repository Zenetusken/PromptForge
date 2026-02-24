<script lang="ts">
    import { Tooltip } from "./index";
    import {
        getStrategyColor,
        STRATEGY_LABELS,
        type StrategyName,
    } from "$lib/utils/strategies";
    import { getTaskTypeColor, type TaskTypeName } from "$lib/utils/taskTypes";
    import {
        getComplexityColor,
        type ComplexityColorMeta,
    } from "$lib/utils/complexity";

    export let type: "strategy" | "task" | "tag" | "complexity";
    export let value: string | null | undefined;
    export let variant: "text" | "pill" | "solid" = "text";
    export let size: "sm" | "xs" = "sm";
    export let showTooltip: boolean = true;

    // Common base classes for all badges
    const baseClasses =
        "font-mono tracking-wider items-center justify-center shrink-0 uppercase inline-flex";

    // Size specific classes
    const sizeClasses = {
        sm: "text-[10px] px-1.5 py-0.5",
        xs: "text-[9px] px-1 py-px",
    };

    $: normalizedValue = value || "Unknown";

    // Get derived color classes based on the type
    $: colorMeta =
        type === "strategy"
            ? getStrategyColor(value)
            : type === "complexity"
              ? getComplexityColor(value)
              : type === "tag"
                ? // We'll give tags a default neon-green/yellow color scheme since they are arbitrary strings
                  {
                      text: "text-neon-green",
                      border: "border-neon-green/30",
                      btnBg: "bg-transparent",
                      chipBg: "bg-transparent",
                  }
                : getTaskTypeColor(value);

    // Get the display text. Strategies use a lookup table, tasks, complexity, and tags use the raw value
    $: displayText =
        type === "strategy"
            ? (STRATEGY_LABELS[value as StrategyName] ?? normalizedValue)
            : type === "tag"
              ? `#${normalizedValue}`
              : normalizedValue;

    // Tooltip text
    $: tooltipText =
        type === "strategy"
            ? `Strategy: ${displayText}`
            : type === "tag"
              ? `Tag: ${normalizedValue}`
              : type === "complexity"
                ? `Complexity: ${displayText}`
                : `Task type: ${displayText}`;

    // Task type is always rendered as plain borderless text — enforced here so
    // every call site picks it up automatically without needing to specify variant.
    $: effectiveVariant = type === "task" ? "text" : variant;

    // Determine the component's final class based on the chosen variant
    $: variantClass = (() => {
        switch (effectiveVariant) {
            case "text":
                // Just colored text with strong font weight
                return `font-bold ${colorMeta.text}`;
            case "pill":
                // Integrated look without background but with solid text color and faint border
                const borderFaint =
                    "border" in colorMeta
                        ? colorMeta.border
                        : "border-current/20";
                return `rounded-md font-semibold border ${borderFaint} bg-transparent ${colorMeta.text}`;
            case "solid":
                // Solid border style (also no background for "integrated look", but perhaps fully bold outline)
                const borderStrong =
                    "border" in colorMeta
                        ? colorMeta.border.replace("-l-", "-")
                        : "border-current";
                return `rounded-full border pb-[1px] font-bold ${colorMeta.text} ${borderStrong} bg-transparent`;
            default:
                return colorMeta.text;
        }
    })();

    $: finalClasses = `${baseClasses} ${sizeClasses[size]} ${variantClass}`;
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
