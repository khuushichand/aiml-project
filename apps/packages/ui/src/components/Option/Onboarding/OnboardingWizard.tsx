/**
 * OnboardingWizard
 *
 * Re-exports OnboardingConnectForm as the sole onboarding implementation.
 * The legacy multi-step wizard was removed as part of the FTUE audit (2026-03-30).
 */

import React from 'react'
import { OnboardingConnectForm } from './OnboardingConnectForm'

type Props = {
  onFinish?: () => void
}

export const OnboardingWizard: React.FC<Props> = ({ onFinish }) => {
  return <OnboardingConnectForm onFinish={onFinish} />
}

export default OnboardingWizard
