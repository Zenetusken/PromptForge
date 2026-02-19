import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import ConfirmModal from './ConfirmModal.svelte';

describe('ConfirmModal', () => {
	beforeEach(() => {
		document.body.innerHTML = '';
	});

	afterEach(() => {
		cleanup();
	});

	it('renders nothing when open=false', () => {
		render(ConfirmModal, { props: { open: false } });
		expect(screen.queryByTestId('confirm-modal')).toBeNull();
	});

	it('renders modal when open=true', () => {
		render(ConfirmModal, {
			props: { open: true, title: 'Test Title', message: 'Test message' },
		});
		expect(screen.getByTestId('confirm-modal')).toBeTruthy();
		expect(screen.getByText('Test Title')).toBeTruthy();
		expect(screen.getByText('Test message')).toBeTruthy();
	});

	it('displays custom button labels', () => {
		render(ConfirmModal, {
			props: { open: true, confirmLabel: 'Delete it', cancelLabel: 'Nope' },
		});
		expect(screen.getByTestId('confirm-modal-confirm').textContent?.trim()).toBe('Delete it');
		expect(screen.getByTestId('confirm-modal-cancel').textContent?.trim()).toBe('Nope');
	});

	it('calls onconfirm when confirm button is clicked', async () => {
		const onconfirm = vi.fn();
		render(ConfirmModal, {
			props: { open: true, onconfirm },
		});
		await fireEvent.click(screen.getByTestId('confirm-modal-confirm'));
		expect(onconfirm).toHaveBeenCalledOnce();
	});

	it('calls oncancel when cancel button is clicked', async () => {
		const oncancel = vi.fn();
		render(ConfirmModal, {
			props: { open: true, oncancel },
		});
		await fireEvent.click(screen.getByTestId('confirm-modal-cancel'));
		expect(oncancel).toHaveBeenCalledOnce();
	});

	it('uses default title when not provided', () => {
		render(ConfirmModal, { props: { open: true } });
		expect(screen.getByText('Are you sure?')).toBeTruthy();
	});
});
