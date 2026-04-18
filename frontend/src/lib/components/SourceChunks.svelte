<script lang="ts">
	import type { DocumentChunk } from '$lib/api';

	interface Props {
		chunks: DocumentChunk[];
	}

	let { chunks }: Props = $props();

	function formatSource(chunk: DocumentChunk): string {
		const parts: string[] = [];
		if (chunk.metadata.course) parts.push(chunk.metadata.course);
		if (chunk.metadata.lecture) parts.push(chunk.metadata.lecture);
		if (chunk.metadata.page_num) parts.push(`p. ${chunk.metadata.page_num}`);
		return parts.length > 0 ? parts.join(' · ') : 'Unknown source';
	}

	function formatScore(score: number | null | undefined): string {
		if (score == null) return '';
		return `${(score * 100).toFixed(0)}%`;
	}
</script>

<details class="sources">
	<summary>sources ({chunks.length})</summary>
	<div class="chunk-list">
		{#each chunks as chunk, i}
			<div class="chunk">
				<div class="chunk-header">
					<span class="chunk-label">Source {i + 1}</span>
					<span class="chunk-source">{formatSource(chunk)}</span>
					{#if chunk.metadata.relevance_score}
						<span class="chunk-score">{formatScore(chunk.metadata.relevance_score)}</span>
					{/if}
				</div>
				<div class="chunk-content">{chunk.content}</div>
			</div>
		{/each}
	</div>
</details>

<style>
	.sources {
		margin-bottom: 0.75rem;
		font-size: var(--fs-small);
	}

	summary {
		cursor: pointer;
		color: var(--text-secondary);
		user-select: none;
	}

	summary:hover {
		color: var(--text);
	}

	.chunk-list {
		margin-top: 0.5rem;
	}

	.chunk {
		border-left: 2px solid var(--border-light);
		padding: 0.3rem 0.5rem;
		margin-bottom: 0.4rem;
	}

	.chunk-header {
		display: flex;
		gap: 0.4rem;
		align-items: baseline;
		margin-bottom: 0.2rem;
		color: var(--text-secondary);
	}

	.chunk-label {
		font-weight: 700;
	}

	.chunk-source {
		flex: 1;
	}

	.chunk-score {
		font-family: var(--font-mono);
		font-size: 0.8em;
	}

	.chunk-content {
		color: var(--text);
		line-height: 1.4;
		white-space: pre-wrap;
	}
</style>
