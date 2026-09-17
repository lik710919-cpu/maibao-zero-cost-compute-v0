import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class AuthorizationIngressGuardTests(unittest.TestCase):
    def test_persistent_authorization_capable_platform_is_forced_into_unified_auth(self):
        from authorization_ingress import AuthorizationIngressGuard, AuthorizationRoute

        guard = AuthorizationIngressGuard()
        decision = guard.classify(
            provider_id="gitlab",
            supports_persistent_authorization=True,
            authorization_required=True,
        )
        self.assertEqual(decision.route, AuthorizationRoute.UNIFIED_REQUIRED)
        self.assertTrue(decision.intercept)

    def test_private_parallel_authorization_path_is_rejected_for_supported_platform(self):
        from authorization_ingress import AuthorizationIngressGuard

        guard = AuthorizationIngressGuard()
        with self.assertRaises(RuntimeError):
            guard.assert_route_allowed(
                provider_id="gitlab",
                supports_persistent_authorization=True,
                authorization_required=True,
                requested_route="private_script",
            )

    def test_activation_is_blocked_until_unified_authorization_record_exists(self):
        from authorization_ingress import AuthorizationIngressGuard

        class EmptyRegistry:
            def get(self, provider_id):
                return None

        guard = AuthorizationIngressGuard(registry=EmptyRegistry())
        with self.assertRaises(RuntimeError):
            guard.assert_activation_allowed(
                provider_id="gitlab",
                supports_persistent_authorization=True,
            )

    def test_activation_is_blocked_for_non_authorized_or_revoked_state(self):
        from authorization_core import AuthorizationRecord, AuthorizationState
        from authorization_ingress import AuthorizationIngressGuard

        class Registry:
            def __init__(self, record):
                self.record = record

            def get(self, provider_id):
                return self.record

        for state in (
            AuthorizationState.UNAUTHORIZED,
            AuthorizationState.AUTHORIZING,
            AuthorizationState.REAUTH_REQUIRED,
            AuthorizationState.REVOKED_BY_USER,
        ):
            with self.subTest(state=state):
                guard = AuthorizationIngressGuard(
                    registry=Registry(AuthorizationRecord(provider_id="gitlab", state=state))
                )
                with self.assertRaises(RuntimeError):
                    guard.assert_activation_allowed(
                        provider_id="gitlab",
                        supports_persistent_authorization=True,
                    )

    def test_authorized_platform_passes_activation_guard(self):
        from authorization_core import AuthorizationRecord, AuthorizationState
        from authorization_ingress import AuthorizationIngressGuard

        class Registry:
            def get(self, provider_id):
                return AuthorizationRecord(provider_id=provider_id, state=AuthorizationState.AUTHORIZED)

        guard = AuthorizationIngressGuard(registry=Registry())
        record = guard.assert_activation_allowed(
            provider_id="gitlab",
            supports_persistent_authorization=True,
        )
        self.assertEqual(record.state, AuthorizationState.AUTHORIZED)

    def test_platform_without_persistent_authorization_support_may_use_exception_route(self):
        from authorization_ingress import AuthorizationIngressGuard, AuthorizationRoute

        guard = AuthorizationIngressGuard()
        decision = guard.classify(
            provider_id="legacy-provider",
            supports_persistent_authorization=False,
            authorization_required=True,
        )
        self.assertEqual(decision.route, AuthorizationRoute.EXCEPTION_ALLOWED)
        self.assertFalse(decision.intercept)

    def test_platform_needing_no_authorization_is_not_forced_through_auth_center(self):
        from authorization_ingress import AuthorizationIngressGuard, AuthorizationRoute

        guard = AuthorizationIngressGuard()
        decision = guard.classify(
            provider_id="public-noauth",
            supports_persistent_authorization=False,
            authorization_required=False,
        )
        self.assertEqual(decision.route, AuthorizationRoute.NOT_REQUIRED)
        self.assertFalse(decision.intercept)


if __name__ == "__main__":
    unittest.main()
