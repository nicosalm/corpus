<script lang="ts">
	interface Props {
		onsubmit: (question: string) => void;
		disabled?: boolean;
	}

	let { onsubmit, disabled = false }: Props = $props();
	let question = $state('');

	function handleSubmit(e: Event) {
		e.preventDefault();
		const q = question.trim();
		if (!q || disabled) return;
		onsubmit(q);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			handleSubmit(e);
		}
	}
</script>

<form onsubmit={handleSubmit} class="query-form">
	<input
		type="text"
		bind:value={question}
		onkeydown={handleKeydown}
		placeholder="ask a question about your notes..."
		{disabled}
	/>
	<button type="submit" disabled={disabled || !question.trim()}>ask</button>
</form>

<style>
	.query-form {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}

	input {
		flex: 1;
		padding: 0.35rem 0.5rem;
		border: 1px solid var(--border);
		background: white;
		color: var(--text);
		outline: none;
	}

	input:focus {
		border-color: var(--text);
	}

	input::placeholder {
		color: var(--border);
	}

	button {
		padding: 0.35rem 0.75rem;
		border: 1px solid var(--border);
		background: var(--code-bg);
		color: var(--text);
	}

	button:hover:not(:disabled) {
		background: var(--border-light);
		border-color: var(--text);
	}

	button:disabled {
		opacity: 0.4;
		cursor: default;
	}
</style>
