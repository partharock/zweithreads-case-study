package com.autotech.aaos.contactscache.integration;

import static org.junit.Assert.fail;

import androidx.test.ext.junit.runners.AndroidJUnit4;

import com.autotech.aaos.contactscache.android.ContactsCacheAccessEnforcer;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.Set;

@RunWith(AndroidJUnit4.class)
public final class ContactsCacheAccessEnforcerTest {

    @Test
    public void enforceReadAccess_allowsConfiguredUid() {
        ContactsCacheAccessEnforcer enforcer = new ContactsCacheAccessEnforcer(
                Set.of(2000),
                Set.of(2000),
                () -> 2000
        );

        enforcer.enforceReadAccess();
        enforcer.enforceWriteAccess();
    }

    @Test
    public void enforceReadAccess_rejectsUnknownUid() {
        ContactsCacheAccessEnforcer enforcer = new ContactsCacheAccessEnforcer(
                Set.of(1000),
                Set.of(1000),
                () -> 2000
        );

        try {
            enforcer.enforceReadAccess();
            fail("Expected SecurityException for unauthorized read uid");
        } catch (SecurityException expected) {
            // expected
        }
    }

    @Test
    public void enforceWriteAccess_rejectsUnknownUid() {
        ContactsCacheAccessEnforcer enforcer = new ContactsCacheAccessEnforcer(
                Set.of(2000),
                Set.of(1000),
                () -> 2000
        );

        try {
            enforcer.enforceWriteAccess();
            fail("Expected SecurityException for unauthorized write uid");
        } catch (SecurityException expected) {
            // expected
        }
    }
}
