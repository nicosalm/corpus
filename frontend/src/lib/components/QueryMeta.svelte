<script lang="ts">
	interface Props {
		processingTimeMs: number;
		costCents: number;
		chunksUsed: number;
		cached?: boolean;
	}

	let { processingTimeMs, costCents, chunksUsed, cached = false }: Props = $props();

	let timeFormatted = $derived(
		processingTimeMs >= 1000
			? `${(processingTimeMs / 1000).toFixed(1)}s`
			: `${Math.round(processingTimeMs)}ms`
	);
</script>

<p class="meta">
	{chunksUsed} sources · {timeFormatted} · ${costCents.toFixed(4)}{#if cached} · cached{/if}
</p>

<style>
	.meta {
		font-size: var(--fs-small);
		color: var(--text-secondary);
		margin-bottom: 0.5rem;
	}
</style>
