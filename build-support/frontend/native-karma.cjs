/* AmbisGIS bounded native suite: keep owned assertions and the Chromium sandbox. */
const fs = require("fs");
const path = require("path");

module.exports = function configure(config) {
    const client = fs.realpathSync(process.env.AMBISGIS_NATIVE_CLIENT);
    const resultDir = fs.realpathSync(process.env.AMBISGIS_NATIVE_OUTPUT);
    const entry = path.join(resultDir, "entry.js");
    const frameworkRoot = fs.realpathSync(path.join(client, "node_modules/mapstore"));
    const framework = path.join(frameworkRoot, "web/client");
    const projectRoot = fs.realpathSync(path.join(client, "node_modules/@mapstore/project"));
    process.env.BABEL_ENV = "test";
    const getTestConfig = require(path.join(projectRoot, "types/standard/config/testConfig.js"));
    const native = getTestConfig({
        files: [
            entry,
            { pattern: path.join(framework, "test-resources/**/*"), included: false },
            { pattern: path.join(framework, "translations/**/*"), included: false }
        ],
        path: [path.join(client, "js"), framework],
        basePath: client,
        testFile: entry,
        singleRun: true,
        browsers: ["AmbisGISChromeHeadless"],
        alias: {
            "@js": path.join(client, "js"),
            "@mapstore/framework": framework
        }
    });
    // Framework assertions use their original standalone fixture URLs.
    const relativeFramework = path.relative(client, framework).split(path.sep).join("/");
    const servedFramework = relativeFramework.startsWith("../")
        ? "/absolute" + framework + "/"
        : "/base/" + relativeFramework + "/";
    native.proxies = {
        ...native.proxies,
        "/base/web/client/test-resources/": servedFramework + "test-resources/",
        "/base/web/client/translations/": servedFramework + "translations/"
    };
    native.customLaunchers = {
        AmbisGISChromeHeadless: {
            base: "ChromeHeadless",
            flags: ["--headless=new", "--use-angle=swiftshader", "--disable-dev-shm-usage"]
        }
    };
    // Explicit module search makes the generated external entry independent of its path.
    native.webpack.resolve.modules = [path.join(client, "node_modules"), "node_modules"];
    native.webpack.resolveLoader = { modules: [path.join(client, "node_modules"), "node_modules"] };
    native.reporters = ["mocha", "junit", "coverage"];
    native.junitReporter = { outputDir: resultDir, outputFile: "junit.xml", useBrowserName: false };
    native.coverageReporter = {
        ...native.coverageReporter,
        dir: path.join(resultDir, "coverage")
    };
    native.hostname = "127.0.0.1";
    native.listenAddress = "127.0.0.1";
    native.port = Number(process.env.AMBISGIS_NATIVE_PORT || 19876);
    native.autoWatch = false;
    config.set(native);
};
