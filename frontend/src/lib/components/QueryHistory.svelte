<script lang="ts">
	import { loadHistory, clearHistory, type HistoryEntry } from '$lib/history';

	interface Props {
		onselect: (entry: HistoryEntry) => void;
	}

	let { onselect }: Props = $props();
	let entries = $state<HistoryEntry[]>(loadHistory());

	export function refresh() {
		entries = loadHistory();
	}

	function handleClear() {
		clearHistory();
		entries = [];
	}

	function formatTime(timestamp: number): string {
		const d = new Date(timestamp);
		const now = new Date();
		if (d.toDateString() === now.toDateString()) {
			return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
		}
		return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
	}

	$effect(() => {
		const interval = setInterval(refresh, 5000);
		return () => clearInterval(interval);
	});
</script>

{#if entries.length > 0}
	<nav class="history">
		<div class="header">
			<span class="title">history</span>
			<button class="clear" onclick={handleClear}>clear</button>
		</div>
		<div class="entries">
			{#each entries as entry}
				<button class="entry" onclick={() => onselect(entry)}>
					<span class="question">{entry.question}</span>
					<span class="time">{formatTime(entry.timestamp)}</span>
				</button>
			{/each}
		</div>
	</nav>
{:else}
	<nav class="history">
		<span class="title empty">no history yet</span>
	</nav>
{/if}

<style>
	.history {
		font-size: var(--fs-small);
	}

	.header {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		margin-bottom: 0.4rem;
	}

	.title {
		color: var(--text-secondary);
		font-weight: 700;
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.title.empty {
		font-weight: 400;
		text-transform: none;
		letter-spacing: normal;
	}

	.entries {
		display: flex;
		flex-direction: column;
	}

	.entry {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.3rem;
		padding: 0.25rem 0.4rem;
		border: none;
		background: none;
		text-align: left;
		color: var(--text);
		font-size: var(--fs-small);
		border-radius: 3px;
	}

	.entry:hover {
		background: var(--code-bg);
	}

	.question {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		flex: 1;
		min-width: 0;
	}

	.time {
		color: var(--text-secondary);
		white-space: nowrap;
		flex-shrink: 0;
		font-size: 0.7rem;
	}

	.clear {
		border: none;
		background: none;
		color: var(--text-secondary);
		font-size: 0.7rem;
		padding: 0;
	}

	.clear:hover {
		color: #c44;
	}
</style>
