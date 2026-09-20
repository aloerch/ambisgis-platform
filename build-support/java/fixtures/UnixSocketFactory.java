package org.ambisgis.probe;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.Socket;
import java.net.SocketAddress;
import java.net.StandardProtocolFamily;
import java.net.UnixDomainSocketAddress;
import java.nio.channels.Channels;
import java.nio.channels.SocketChannel;
import javax.net.SocketFactory;

/** Experimental JDBC test transport only. The parent process bounds test time;
 * socket SO_TIMEOUT is not emulated. No TCP fallback or production use. */
public final class UnixSocketFactory extends SocketFactory {
    private final String path;
    public UnixSocketFactory(String path) { this.path = path; }
    @Override public Socket createSocket() { return new UnixSocket(path); }
    @Override public Socket createSocket(String h, int p) throws IOException { throw new IOException("TCP forbidden"); }
    @Override public Socket createSocket(String h, int p, InetAddress l, int lp) throws IOException { throw new IOException("TCP forbidden"); }
    @Override public Socket createSocket(InetAddress h, int p) throws IOException { throw new IOException("TCP forbidden"); }
    @Override public Socket createSocket(InetAddress h, int p, InetAddress l, int lp) throws IOException { throw new IOException("TCP forbidden"); }
    private static final class UnixSocket extends Socket {
        private final String path;
        private SocketChannel channel;
        private boolean closed;
        UnixSocket(String path) { this.path = path; }
        @Override public void connect(SocketAddress ignored, int timeout) throws IOException {
            if (channel != null) throw new IOException("Already connected");
            channel = SocketChannel.open(StandardProtocolFamily.UNIX);
            channel.connect(UnixDomainSocketAddress.of(path));
        }
        @Override public void connect(SocketAddress address) throws IOException { connect(address, 0); }
        @Override public InputStream getInputStream() throws IOException { return Channels.newInputStream(channel); }
        @Override public OutputStream getOutputStream() throws IOException { return Channels.newOutputStream(channel); }
        @Override public synchronized void close() throws IOException { closed = true; if (channel != null) channel.close(); }
        @Override public boolean isConnected() { return channel != null && channel.isConnected(); }
        @Override public boolean isClosed() { return closed; }
        @Override public void setTcpNoDelay(boolean on) { }
        @Override public void setKeepAlive(boolean on) { }
        @Override public void setSoTimeout(int timeout) { }
        @Override public int getSoTimeout() { return 0; }
        @Override public void setReceiveBufferSize(int size) { }
        @Override public void setSendBufferSize(int size) { }
        @Override public int getReceiveBufferSize() { return 65536; }
        @Override public int getSendBufferSize() { return 65536; }
        @Override public InetAddress getInetAddress() { return InetAddress.getLoopbackAddress(); }
    }
}
