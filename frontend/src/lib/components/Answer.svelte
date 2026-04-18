<script lang="ts">
	import Markdown from './Markdown.svelte';

	interface Props {
		answer: string;
	}

	let { answer }: Props = $props();
</script>

<div class="answer">
	<Markdown content={answer} />
</div>

<style>
	.answer {
		margin-bottom: 0.75rem;
	}
</style>
