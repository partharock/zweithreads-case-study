package com.autotech.aaos.contactscache.core.util;

public interface Clock {
    long nowMs();

    Clock SYSTEM = System::currentTimeMillis;
}
