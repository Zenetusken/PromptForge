<script lang="ts">
  import OnboardingWizard from './OnboardingWizard.svelte';
  import Modal from '$lib/components/shared/Modal.svelte';

  interface Props {
    onComplete: () => void;
    githubConnected?: boolean;
    repoLinked?: boolean;
    providerReady?: boolean;
    providerType?: string;
  }
  const { onComplete, githubConnected = false, repoLinked = false, providerReady = false, providerType = 'unknown' }: Props = $props();
</script>

<!-- Full-screen onboarding overlay -->
<Modal backdropOpacity={90}>
  <div class="flex items-center justify-center h-full pointer-events-auto">
    <OnboardingWizard {onComplete} {githubConnected} {repoLinked} {providerReady} {providerType} />
  </div>
</Modal>
