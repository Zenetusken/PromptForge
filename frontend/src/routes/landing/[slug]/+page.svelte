<script lang="ts">
  import Navbar from '$lib/components/landing/Navbar.svelte';
  import Footer from '$lib/components/landing/Footer.svelte';
  import type { ContentPage } from '$lib/content/types';

  let { data } = $props();
  const page: ContentPage = $derived(data.page);
</script>

<svelte:head>
  <title>{page.title} — Project Synthesis</title>
  <meta name="description" content={page.description} />
</svelte:head>

<Navbar />

<main id="main-content" class="content-page">
  <h1 class="content-page__title">{page.title}</h1>
</main>

<Footer />

<style>
  .content-page {
    max-width: 1120px;
    margin: 0 auto;
    padding: 52px 16px 40px;
  }
  .content-page__title {
    font-family: var(--font-display);
    font-size: 20px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--color-text-primary);
  }
</style>
