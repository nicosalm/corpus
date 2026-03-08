<script lang="ts">
	import FileUpload from '$lib/components/FileUpload.svelte';
</script>

<div class="upload-content">
	<h1>upload</h1>
	<p>Upload PDF files to add them to your knowledge base. They'll be chunked, embedded, and indexed for querying.</p>

	<FileUpload />
</div>

<style>
	.upload-content {
		max-width: 72ch;
	}
</style>
