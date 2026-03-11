<script lang="ts">
  import OnboardingWizard from './OnboardingWizard.svelte';

  interface Props {
    onComplete: () => void;
    githubConnected?: boolean;
  }
  const { onComplete, githubConnected = false }: Props = $props();
</script>

<!-- Full-screen onboarding overlay -->
<div class="fixed inset-0 z-50 flex items-center justify-center bg-bg-primary/90">
  <OnboardingWizard {onComplete} {githubConnected} />
</div>
