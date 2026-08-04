package com.everydayadvertise.tv.api

import java.security.cert.X509Certificate
import javax.net.ssl.*

/**
 * TEMPORARY WORKAROUND for old Android TV devices (Android 8.0 from 2020)
 * that don't have updated root CA certificates for Cloudflare/Google Trust Services.
 * 
 * SECURITY NOTE: This bypasses SSL certificate validation. Only use on trusted networks.
 */
object TrustAllCerts {
    private val trustManager = object : X509TrustManager {
        override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
        override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
        override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
    }

    fun getUnsafeSSLSocketFactory(): SSLSocketFactory {
        val sslContext = SSLContext.getInstance("TLS")
        sslContext.init(null, arrayOf<TrustManager>(trustManager), java.security.SecureRandom())
        return sslContext.socketFactory
    }

    fun getTrustManager(): X509TrustManager {
        return trustManager
    }

    fun getAllTrustingHostnameVerifier(): HostnameVerifier {
        return HostnameVerifier { _, _ -> true }
    }

    fun getSSLContext(): SSLContext {
        val sslContext = SSLContext.getInstance("TLS")
        sslContext.init(null, arrayOf<TrustManager>(trustManager), java.security.SecureRandom())
        return sslContext
    }
}
