package com.autotech.aaos.contactscache.core.store;

public interface StoreTransaction extends AutoCloseable {
    void commit();

    @Override
    void close();
}
