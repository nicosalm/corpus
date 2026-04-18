<script lang="ts">
	import { uploadPdfs, type IngestResponse } from '$lib/api';

	let fileInput: HTMLInputElement;
	let dragover = $state(false);
	let uploading = $state(false);
	let result = $state<IngestResponse | null>(null);
	let error = $state('');

	async function handleFiles(files: FileList | null) {
		if (!files || files.length === 0) return;

		uploading = true;
		error = '';
		result = null;

		try {
			result = await uploadPdfs(files);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Upload failed';
		} finally {
			uploading = false;
		}
	}

	function handleDrop(e: DragEvent) {
		e.preventDefault();
		dragover = false;
		handleFiles(e.dataTransfer?.files ?? null);
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		dragover = true;
	}

	function handleDragLeave() {
		dragover = false;
	}
</script>

<div
	class="drop-zone"
	class:dragover
	class:uploading
	role="button"
	tabindex="0"
	ondrop={handleDrop}
	ondragover={handleDragOver}
	ondragleave={handleDragLeave}
	onclick={() => fileInput.click()}
	onkeydown={(e) => e.key === 'Enter' && fileInput.click()}
>
	<input
		bind:this={fileInput}
		type="file"
		accept=".pdf"
		multiple
		hidden
		onchange={(e) => handleFiles(e.currentTarget.files)}
	/>

	{#if uploading}
		<span>processing...</span>
	{:else}
		<span>drop PDFs here or click to select</span>
	{/if}
</div>

{#if result}
	<div class="result">
		<p>
			{result.files_processed} file{result.files_processed !== 1 ? 's' : ''} processed ·
			{result.chunks_created} chunks · {result.concepts_extracted} concepts ·
			{(result.processing_time_ms / 1000).toFixed(1)}s
		</p>
		{#if result.errors && result.errors.length > 0}
			<div class="errors">
				{#each result.errors as err}
					<p class="error">{err}</p>
				{/each}
			</div>
		{/if}
	</div>
{/if}

{#if error}
	<p class="error">{error}</p>
{/if}

<style>
	.drop-zone {
		border: 1px dashed var(--border);
		padding: 1.5rem;
		text-align: center;
		color: var(--text-secondary);
		cursor: pointer;
		margin-bottom: 0.75rem;
		font-size: var(--fs-small);
	}

	.drop-zone:hover,
	.drop-zone.dragover {
		border-color: var(--text);
		color: var(--text);
		background: var(--code-bg);
	}

	.drop-zone.uploading {
		cursor: wait;
		border-style: solid;
	}

	.result {
		font-size: var(--fs-small);
		color: var(--text-secondary);
		margin-bottom: 0.5rem;
	}

	.error {
		color: #c44;
		font-size: var(--fs-small);
	}

	.errors {
		margin-top: 0.3rem;
	}
</style>
